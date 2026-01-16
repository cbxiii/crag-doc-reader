"""Semantic Retrieval Demo

This script is a direct conversion of the `semantic_retrieval_demo.ipynb` notebook.

Features:
- Extract sentences from MD files with source tracking
- Generate embeddings using Qwen3-Embedding via Ollama
- Store embeddings in FAISS for fast similarity search
- Perform semantic search with cosine similarity
- Synthesize answers using an LLM (Llama3.2)

Note: This file is intended as a runnable script; adjust model names, installation,
and local Ollama / FAISS configuration as needed for your environment.
"""

# Install required packages (run manually if needed):
# pip install ollama faiss-cpu nltk numpy

import json
from pathlib import Path
from typing import List, Tuple

import ollama
import faiss

from vector_store_utils import (
    SentenceWithSource,
    get_embedding,
    load_existing_data,
)


# --- Pydantic models for structured LLM responses ---
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent
from typing import Optional


class SourceItem(BaseModel):
    text: str
    file_title: str
    section_header: Optional[str]
    score: Optional[float]


class AnswerModel(BaseModel):
    summary: str
    sources: List[SourceItem]
    references_included: bool = False


# Helper to detect reference-like headers
def is_reference_section(header: str) -> bool:
    if not header:
        return False
    h = header.strip().lower()
    return any(k in h for k in ("references", "literature cited", "bibliography", "works cited"))

def search(index: faiss.Index, sentences: List[SentenceWithSource], query: str, top_k: int = 5) -> List[Tuple[SentenceWithSource, float]]:
    """Search for most similar sentences to query

    Args:
        index (faiss.Index): FAISS index (must be loaded)
        sentences (List[SentenceWithSource]): Sentences list aligned with embeddings
        query (str): Query string
        top_k (int): Number of top results

    Returns:
        List[Tuple[SentenceWithSource, float]]
    """
    if index is None:
        raise ValueError("No index loaded. Process files first.")

    # Get and normalize query embedding
    query_embedding = get_embedding(query, model="qwen3-embedding:0.6b")
    if query_embedding is None:
        return []

    query_embedding = query_embedding.reshape(1, -1)
    faiss.normalize_L2(query_embedding)

    # Search
    scores, indices = index.search(query_embedding, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < len(sentences):
            results.append((sentences[idx], float(score)))

    return results


def synthesize_answer(query: str, results: List[Tuple[SentenceWithSource, float]], model: str = "llama3:8b") -> str:
    """Use LLM to synthesize a structured answer (JSON) from relevant sentences.

    Returns the raw text response from the model (expected JSON). Caller should parse
    with the `AnswerModel` Pydantic schema.
    """

    context = "\n\n".join([
        f"[{sent.file_title}] {sent.section_header}\n{sent.text}"
        for sent, score in results
    ])

    # Instruction: return JSON matching our simple pydantic schema
    prompt = f"""
You are a concise subject-matter expert. Given the context snippets below, produce a JSON object with the following keys: `summary` (short answer), `sources` (an array of objects with keys `text`, `file_title`, `section_header`, and `score`), and `references_included` (boolean).

Only include sources that you directly used in the summary. Do NOT invent or hallucinate sources — every listed source must match one of the provided context snippets. If you cannot answer from the provided context, set `summary` to an empty string and provide an empty `sources` array.

Context snippets (each is one passage you may cite):
{context}

User question: {query}

Return ONLY valid JSON that conforms to the schema. Do not add any explanatory text.
"""

    try:
        response = ollama.generate(model=model, prompt=prompt)
        return response.get('response', '')
    except Exception as e:
        return json.dumps({"summary": "", "sources": [], "references_included": False, "error": str(e)})


def main():
    # Load existing data
    sentences, embeddings, index, processed_files = load_existing_data()
    print(f"Previously processed files: {processed_files}")

    # Batch-run queries from JSON and synthesize responses
    if index is not None and len(sentences) > 0:
        queries_path = Path("queries/chatgpt_queries.json")
        OUTPUT_DIR = Path("responses")
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_path = OUTPUT_DIR / "01_16_2026_chatgpt_query_responses.json"
        responses = []

        try:
            with open(queries_path, 'r', encoding='utf-8') as qf:
                queries_obj = json.load(qf)
        except Exception as e:
            print(f"Error loading queries file {queries_path}: {e}")
            queries_obj = []

        import time

        for idx, item in enumerate(queries_obj, 1):
            qtext = item['query'] if isinstance(item, dict) and 'query' in item else (item if isinstance(item, str) else "")
            if not qtext:
                continue

            print(f"[{idx}/{len(queries_obj)}] Query: {qtext}")

            try:
                results = search(index, sentences, qtext, top_k=5)
            except Exception as e:
                print(f"Search error for query: {e}")
                responses.append({"query": qtext, "error": str(e)})
                continue

            # Filter out reference-like sections unless the user explicitly asks for references
            wants_references = any(k in qtext.lower() for k in ("reference", "references", "literature cited", "bibliography"))
            filtered_results = [r for r in results if not is_reference_section(r[0].section_header)]
            if not filtered_results and wants_references:
                # if user asked for references, allow reference sections
                filtered_results = results

            for i, (sentence, score) in enumerate(filtered_results, 1):
                print(f"{i}. Score: {score:.4f} | File: {sentence.file_title} | Section: {sentence.section_header}")

            model = "llama3.2:3b"
            raw_response = synthesize_answer(qtext, filtered_results, model)

            # Try to parse structured JSON into our Pydantic model and validate sources
            parsed_struct = None
            parse_error = None
            try:
                parsed = json.loads(raw_response)
                parsed_struct = AnswerModel(**parsed)

                # Validate that every cited source in parsed_struct.sources exists in retrieved candidates
                retrieved_texts = {s.text for s, _ in filtered_results}
                mismatches = []
                for src in parsed_struct.sources:
                    if src.text not in retrieved_texts:
                        mismatches.append({"text": src.text, "file_title": src.file_title})

                validation_notes = {
                    "mismatched_cited_sources": mismatches,
                    "references_were_requested": wants_references,
                }

            except (json.JSONDecodeError, ValidationError) as e:
                parse_error = str(e)
                parsed_struct = None
                validation_notes = {"parse_error": parse_error, "references_were_requested": wants_references}

            responses.append({
                "query": qtext,
                "raw_response": raw_response,
                "parsed": parsed_struct.dict() if parsed_struct is not None else None,
                "top_results": [
                    {"text": s.text, "file_title": s.file_title, "section_header": s.section_header, "score": score}
                    for s, score in filtered_results
                ],
                "validation": validation_notes,
            })

            # brief pause to avoid hammering LLM/embedding service
            time.sleep(1)

        try:
            with open(out_path, 'w', encoding='utf-8') as outf:
                json.dump(responses, outf, indent=2, ensure_ascii=False)
            print(f"Saved {len(responses)} query responses to {out_path}")
        except Exception as e:
            print(f"Error saving responses to {out_path}: {e}")

    else:
        print("No index or sentences available for search/synthesis.")


if __name__ == "__main__":
    main()

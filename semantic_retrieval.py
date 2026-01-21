"""Semantic Retrieval 

This script is a direct conversion of the `semantic_retrieval_demo.ipynb` notebook.

Features:
- Perform semantic search with cosine similarity
- Synthesize answers using an LLM 
"""

import json
from pathlib import Path
from typing import List, Tuple
import faiss
import time
from vector_store_utils import (
    SentenceWithSource,
    get_embedding,
    load_existing_data,
)
from pydantic import BaseModel
from pydantic_ai import Agent
import dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

dotenv.load_dotenv()

class SourceItem(BaseModel):
    text: str
    file_title: str
    section_header: str
    score: float

class AnswerModel(BaseModel):
    summary: str
    sources: List[SourceItem]

# Helper to detect reference-like headers
# def is_reference_section(header: str) -> bool:
#     if not header:
#         return False
#     h = header.strip().lower()
#     return any(k in h for k in ("references", "literature cited", "bibliography", "works cited"))

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

PROMPT_TEMPLATE = """
You are a concise subject-matter expert. Given the context snippets below, produce a JSON object with the following keys: `summary` (short answer), `sources` (an array of objects with keys `text`, `file_title`, `section_header`, and `score`).

Only include sources that you directly used in the summary. Do NOT invent or hallucinate sources — every listed source must match one of the provided context snippets. If you cannot answer from the provided context, set `summary` to an empty string and provide an empty `sources` array.

Context snippets (each is one passage you may cite):
{context}

User question: {query}

Return ONLY valid JSON that conforms to the schema. Do not add any explanatory text.
"""

def synthesize_answer(query: str, results: List[Tuple[SentenceWithSource, float]]) -> str:
    """Use LLM to synthesize a structured answer (JSON) from relevant sentences.

    Returns the raw text response from the model (expected JSON). Caller should parse
    with the `AnswerModel` Pydantic schema.
    """

    context = "\n\n".join([
        f"[{sent.file_title}] {sent.section_header}\n{sent.text}"
        for sent, score in results
    ])

    prompt = PROMPT_TEMPLATE.format(context=context, query=query)

    try:
        answer_agent = Agent(  
            model='openai:gpt-4o-mini',
            output_type=AnswerModel,
            system_prompt=prompt,
        )
        response = answer_agent.run_sync(prompt)
        return response.output
    except Exception as e:
        return json.dumps({"summary": "", "sources": [], "error": str(e)})


def main():
    # Load existing data
    sentences, embeddings, index, processed_files = load_existing_data()
    print(f"Previously processed files: {processed_files}")

    if index is not None and len(sentences) > 0:
        queries_path = Path("queries/chatgpt_queries.json")
        OUTPUT_DIR = Path("responses")
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now(ZoneInfo("Pacific/Honolulu")).strftime("%m_%d_%Y_%I:%M%p")
        out_path = OUTPUT_DIR / f"{timestamp}_chatgpt_queries_responses.json"
        responses = []

        try:
            with open(queries_path, 'r', encoding='utf-8') as qf:
                queries_obj = json.load(qf)
        except Exception as e:
            print(f"Error loading queries file {queries_path}: {e}")
            queries_obj = []

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

            for i, (sentence, score) in enumerate(results, 1):
                print(f"{i}. Score: {score:.4f} | File: {sentence.file_title} | Section: {sentence.section_header}")

            try:
                answer = synthesize_answer(qtext, results)
            except Exception as e:
                answer = f"Error during synthesis: {e}"

            responses.append({
                "query": qtext,
                "response": answer,
                "top_results": [
                    {"text": s.text, "file_title": s.file_title, "section_header": s.section_header, "score": score}
                    for s, score in results
                ]
            })

            time.sleep(1)

        try:
            out_obj = {
                "prompt": PROMPT_TEMPLATE,
                "responses": responses
            }
            with open(out_path, 'w', encoding='utf-8') as outf:
                json.dump(out_obj, outf, indent=2, ensure_ascii=False)
            print(f"Saved {len(responses)} query responses to {out_path}")
        except Exception as e:
            print(f"Error saving responses to {out_path}: {e}")

    else:
        print("No index or sentences available for search/synthesis.")

if __name__ == "__main__":
    main()

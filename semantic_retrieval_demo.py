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
    """Use LLM to synthesize answer from relevant sentences"""
    context = "\n\n".join([
        f"[{sent.file_title}] {sent.section_header}\n{sent.text}"
        for sent, score in results
    ])

    prompt = f"""Based on the following context, answer the question. Be specific and cite sources.
            Answer like an established expert who has been researching this topic for 20+ years.

            Context:
            {context}

            Question: {query}

            Answer:"""

    try:
        response = ollama.generate(model=model, prompt=prompt)
        return response['response']
    except Exception as e:
        return f"Error: {e}"


def main():
    # Load existing data
    sentences, embeddings, index, processed_files = load_existing_data()
    print(f"Previously processed files: {processed_files}")

    # Batch-run queries from JSON and synthesize responses
    if index is not None and len(sentences) > 0:
        queries_path = Path("queries/chatgpt_queries.json")
        OUTPUT_DIR = Path("responses")
        OUTPUT_DIR.mkdir(exist_ok=True)
        out_path = OUTPUT_DIR / "chatgpt_query_responses.json"
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

            for i, (sentence, score) in enumerate(results, 1):
                print(f"{i}. Score: {score:.4f} | File: {sentence.file_title} | Section: {sentence.section_header}")

            model = "llama3.2:3b"
            try:
                answer = synthesize_answer(qtext, results, model)
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

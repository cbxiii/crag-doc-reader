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
from pydantic import BaseModel, Field
from pydantic_ai import Agent
import dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

dotenv.load_dotenv()

class SourceItem(BaseModel):
    text: str = Field(description="The exact text segment cited.")
    file_title: str = Field(description="Title of the source file.")
    section_header: str = Field(description="Header of the section.")
    score: float = Field(description="Relevance score of the text segment.")

class AnswerModel(BaseModel):
    summary: str = Field(description="Concise summary of the answer.")
    sources: List[SourceItem] = Field(description="List of source items directly used to generate the summary.")

# Helper to detect reference-like headers
def is_invalid_source(header: str) -> bool:
    if not header:
        return False
    h = header.strip().lower()
    forbidden_terms = ["references", "works cited", "bibliography", "literature cited"]
    return any(term in h for term in forbidden_terms)

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
    You are a concise subject-matter expect in the field. 
    Use to provided context to answer the user's question as accurately as possible. 
    If the answer is not in the context, state that you cannot answer. 
    Do NOT hallucinate sources.
"""

answer_agent = Agent(  
    model='openai:gpt-4o-mini',
    output_type=AnswerModel,
    instructions=PROMPT_TEMPLATE,
)

def synthesize_answer(query: str, results: List[Tuple[SentenceWithSource, float]]) -> AnswerModel:
    """
    Synthesizes an answer using the Answer Agent.
    Returns an AnswerModel Object.
    """

    context = "\n\n".join([
        f"--- Source (Score: {score:.4f}) ---\n"
        f"File: {sent.file_title}\n"
        f"Section: {sent.section_header}\n"
        f"Text: {sent.text}"
        for sent, score in results
    ])

    user_prompt = (
        f"User Question: {query}\n\n"
        f"Context: \n{context}\n\n"
    )
    try:
        response = answer_agent.run_sync(user_prompt)
        return response.output
    except Exception as e:
        return AnswerModel(summary=f"Error generating response: {e}.", sources=[])

def synthesize_with_validation(query: str,
    initial_results: List[Tuple[SentenceWithSource, float]],
    max_retries: int = 2) -> AnswerModel:
    curr_context = initial_results

    for attempt in range(max_retries + 1):
        answer: AnswerModel = synthesize_answer(query, curr_context)
        invalid_source_indices = []

        for i, source in enumerate(answer.sources):
            if is_invalid_source(source.section_header):
                invalid_source_indices.append(i)
                print(f"Flagged invalid source: '{source.file_title}' ({source.section_header})")
        
        if not invalid_source_indices:
            return answer
        
        if attempt == max_retries:
            print("Max retries reached. Returning last answer.")
            answer.sources = [
                s for i, s in enumerate(answer.sources) if i not in invalid_source_indices
            ]
            return answer
        
        print(f"Validation failed. Removing {len(invalid_source_indices)} invalid sources and regenerating...")

        invalid_source_texts = {answer.sources[i].text for i in invalid_source_indices}
        
        curr_context = [
            (sent, score) for sent, score in curr_context
            if sent.text not in invalid_source_texts
        ]
    
    return answer


def main():
    # Load existing data
    sentences, embeddings, index, processed_files = load_existing_data()
    print(f"Previously processed files: {processed_files}")

    if index is None or len(sentences) == 0:
        print("No existing index or sentences found. Please process files first.")
        return

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

        answer = synthesize_with_validation(qtext, results)

        response_entry = {
            "query": qtext,
            "response": answer.summary,
            "sources": [source.model_dump() for source in answer.sources],
            "top_results": [
                {"text": s.text, "file_title": s.file_title, "section_header": s.section_header, "score": score}
                for s, score in results
            ]
        }

        responses.append(response_entry)
        time.sleep(1)

    try:
        out_obj = {
            "meta":{
                "timestamp": timestamp,
                "model": answer_agent.model.model_name,
                "prompt": PROMPT_TEMPLATE},
            "responses": responses
        }
        with open(out_path, 'w', encoding='utf-8') as outf:
            json.dump(out_obj, outf, indent=2, ensure_ascii=False)
        print(f"Saved {len(responses)} query responses to {out_path}")
    except Exception as e:
        print(f"Error saving responses to {out_path}: {e}")

if __name__ == "__main__":
    main()

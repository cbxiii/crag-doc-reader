"""Semantic Retrieval Demo

This script is a direct conversion of the `semantic_retrieval_demo.ipynb` notebook.

Features:
- Extract sentences from MD files with source tracking
- Generate embeddings using Qwen3-Embedding via Ollama
- Store embeddings in FAISS for fast similarity search
- Perform semantic search with cosine similarity
- Synthesize answers using an LLM

Note: This file is intended as a runnable script; adjust model names, installation,
and local Ollama / FAISS configuration as needed for your environment.
"""

# Install required packages (run manually if needed):
# pip install ollama faiss-cpu nltk numpy

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple

import ollama
import numpy as np
import faiss
import nltk

# Download NLTK punkt tokenizer non-interactively (quiet)
nltk.download('punkt', quiet=True)


@dataclass
class SentenceWithSource:
    """Container for a sentence with its source information"""
    text: str
    file_path: str
    file_title: str  # MD file title for tracking
    line_number: int
    section_header: str = ""


def get_embedding(text: str, model: str = "qwen3-embedding:8b") -> np.ndarray:
    """Get embedding vector for text using Ollama

    Args:
        text (str): The text to generate an embedding for
        model (str, optional): The model to use. Defaults to "qwen3-embedding:8b".

    Returns:
        np.ndarray: The embedding vector (float32) or None on error
    """
    try:
        response = ollama.embeddings(model=model, prompt=text)
        return np.array(response['embedding'], dtype=np.float32)
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None


def split_into_sentences(text: str, file_path: str, file_title: str) -> List[SentenceWithSource]:
    """Split text into sentences while tracking source information

    Args:
        text (str): The text to split into sentences
        file_path (str): The path to the file the text is from
        file_title (str): The title of the file

    Returns:
        List[SentenceWithSource]: A list of sentences with source information
    """
    sentences_with_source = []
    lines = text.split('\n')
    current_section = ""

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        # Track section headers
        if line.startswith('#'):
            current_section = line.strip('#').strip()
            continue

        # Skip tables, images, and short lines
        if '|' in line or line.startswith('---') or line.startswith('![]') or line.startswith('Fig.'):
            continue

        # Split into sentences
        sentences = nltk.sent_tokenize(line)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:  # Filter short sentences
                sentences_with_source.append(
                    SentenceWithSource(
                        text=sentence,
                        file_path=file_path,
                        file_title=file_title,
                        line_number=line_num,
                        section_header=current_section,
                    )
                )

    return sentences_with_source


# Storage paths
STORAGE_DIR = Path("vector_store")
STORAGE_DIR.mkdir(exist_ok=True)

EMBEDDINGS_FILE = STORAGE_DIR / "embeddings.npy"
FAISS_INDEX_FILE = STORAGE_DIR / "index.faiss"
METADATA_FILE = STORAGE_DIR / "metadata.json"

print(f"Storage directory: {STORAGE_DIR.absolute()}")


def load_existing_data():
    """Load existing embeddings, index, and metadata if they exist

    Returns:
        Tuple[List[SentenceWithSource], np.ndarray, faiss.Index, set]: sentences, embeddings, index, processed_files
    """
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        embeddings = np.load(EMBEDDINGS_FILE) if EMBEDDINGS_FILE.exists() else None
        index = faiss.read_index(str(FAISS_INDEX_FILE)) if FAISS_INDEX_FILE.exists() else None

        # Reconstruct sentences from metadata
        sentences = [SentenceWithSource(**item) for item in metadata['sentences']]
        processed_files = set(metadata.get('processed_files', []))

        print(f"Loaded {len(sentences)} sentences from {len(processed_files)} files")
        return sentences, embeddings, index, processed_files

    return [], None, None, set()


def save_data(sentences: List[SentenceWithSource], embeddings: np.ndarray, index: faiss.Index, processed_files: set, model: str = "qwen3-embedding:8b"):
    """Save embeddings, FAISS index, and metadata"""
    # Save embeddings
    np.save(EMBEDDINGS_FILE, embeddings)

    # Save FAISS index
    faiss.write_index(index, str(FAISS_INDEX_FILE))

    # Save metadata
    metadata = {
        'sentences': [asdict(s) for s in sentences],
        'processed_files': list(processed_files),
        'embedding_model': model,
        'dimension': embeddings.shape[1],
        'total_sentences': len(sentences),
    }

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved {len(sentences)} sentences, embeddings, and FAISS index")


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

    # Specify MD file to process
    md_file_path = r"output/Dahl-1972-Ecology.reef.algae.AS/Dahl-1972-Ecology.reef.algae.AS.md"
    file_path = Path(md_file_path).resolve()
    file_title = file_path.stem  # Use filename without extension as title

    print(f"File: {file_path}")
    print(f"Title: {file_title}")

    # Check if already processed
    if file_title in processed_files:
        print(f"⚠️ '{file_title}' already processed. Skipping...")
    else:
        print(f"✓ New file - will process")

    # Process new file if not already done
    if file_title not in processed_files:
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract sentences
        new_sentences = split_into_sentences(content, str(file_path), file_title)
        print(f"Extracted {len(new_sentences)} sentences")

        # Generate embeddings
        print("Generating embeddings...")
        new_embeddings = []
        for i, sentence in enumerate(new_sentences):
            if i % 10 == 0:
                print(f"  {i+1}/{len(new_sentences)}")

            embedding = get_embedding(sentence.text, model="qwen3-embedding:0.6b")
            if embedding is not None:
                new_embeddings.append(embedding)
            else:
                # Fallback to zero vector
                print(f"  {i+1}/{len(new_sentences)}: Failed to generate embedding")
                new_embeddings.append(np.zeros(1024, dtype=np.float32))

        new_embeddings = np.vstack(new_embeddings)

        # Normalize for cosine similarity
        faiss.normalize_L2(new_embeddings)

        # Merge with existing data
        if embeddings is not None:
            embeddings = np.vstack([embeddings, new_embeddings])
            sentences.extend(new_sentences)
        else:
            embeddings = new_embeddings
            sentences = new_sentences

        # Rebuild FAISS index
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings)

        # Mark as processed
        processed_files.add(file_title)

        # Save everything
        save_data(sentences, embeddings, index, processed_files)

        print(f"✓ Processed and saved. Total: {len(sentences)} sentences from {len(processed_files)} files")

    # Batch-run queries from JSON and synthesize responses
    if index is not None and len(sentences) > 0:
        queries_path = Path("queries/coral_queries.json")
        out_path = STORAGE_DIR / "query_responses.json"
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

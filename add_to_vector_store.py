"""Add files to vector store

This module provides a small CLI and functions to process a markdown/text
file into sentences, compute embeddings via Ollama, and add them to a
FAISS vector store (saved under `vector_store/`). It follows the same
logic as `semantic_retrieval_demo.py` but is packaged for reuse.

Usage:
    python add_to_vector_store.py /path/to/file.md
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Tuple, Set

import ollama
import numpy as np
import faiss
from vector_store_utils import (
    split_into_sentences,
    get_embedding,
    load_existing_data,
    save_data,
)


def process_and_add(md_path: str) -> None:
    # check if ollama is reachable
    try:
        ollama.list()
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        return

    sentences, embeddings, index, processed_files = load_existing_data()

    path = Path(md_path).resolve()
    if not path.exists():
        print(f"File not found: {path}")
        return

    file_title = path.stem
    if file_title in processed_files:
        print(f"'{file_title}' already processed. Skipping.")
        return

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_sentences = split_into_sentences(content, str(path), file_title)
    if not new_sentences:
        print("No sentences extracted. Nothing to add.")
        return

    print(f"Extracted {len(new_sentences)} sentences from {file_title}")

    new_embeddings_list = []
    dim = None
    model = "qwen3-embedding:0.6b"
    for i, s in enumerate(new_sentences, 1):
        if i % 10 == 0:
            print(f"  processing {i}/{len(new_sentences)}")
        emb = get_embedding(s.text, model=model)
        if emb is None:
            # will fill after we know dim
            new_embeddings_list.append(None)
        else:
            new_embeddings_list.append(emb)
            dim = emb.shape[0]

    if dim is None:
        # all failed — pick a default dimension
        dim = 1024

    # Replace any None with zero vectors
    new_embeddings = np.vstack([(e if e is not None else np.zeros(dim, dtype=np.float32)) for e in new_embeddings_list])

    faiss.normalize_L2(new_embeddings)

    if embeddings is not None:
        if embeddings.shape[1] != new_embeddings.shape[1]:
            print("Existing embeddings dimension differs from new embeddings. Rebuilding with new dimension.")
            # pad or trim existing to match new dim
            old = embeddings
            old_dim = old.shape[1]
            if old_dim < new_embeddings.shape[1]:
                pad = np.zeros((old.shape[0], new_embeddings.shape[1] - old_dim), dtype=np.float32)
                embeddings = np.hstack([old, pad])
            else:
                embeddings = old[:, :new_embeddings.shape[1]]

        embeddings = np.vstack([embeddings, new_embeddings])
        sentences.extend(new_sentences)
    else:
        embeddings = new_embeddings
        sentences = new_sentences

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    processed_files.add(file_title)
    save_data(sentences, embeddings, index, processed_files, model=model)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add a markdown/text file to the FAISS vector store.")
    parser.add_argument('file', help='Path to the markdown or text file to process')
    parser.add_argument('--model', default='qwen3-embedding:0.6b', help='Ollama embedding model')
    args = parser.parse_args()

    process_and_add(args.file, model=args.model)

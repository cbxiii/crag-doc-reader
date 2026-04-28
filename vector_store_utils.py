"""Shared vector-store utilities

Contains the SentenceWithSource dataclass, sentence tokenization,
embedding helper, and load/save helpers for the FAISS + numpy store.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple, Set, Optional

import ollama
import numpy as np
import faiss
import nltk

nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

@dataclass
class SentenceWithSource:
    text: str
    file_path: str
    file_title: str
    line_number: int
    section_header: str = ""


# Storage paths
STORAGE_DIR = Path("/media/volume/crag-vectorstore")
STORAGE_DIR.mkdir(exist_ok=True)

EMBEDDINGS_FILE = STORAGE_DIR / "embeddings.npy"
FAISS_INDEX_FILE = STORAGE_DIR / "index.faiss"
METADATA_FILE = STORAGE_DIR / "metadata.json"


def get_embedding(text: str) -> Optional[np.ndarray]:
    model: str = "qwen3-embedding:0.6b"
    try:
        resp = ollama.embeddings(model=model, prompt=text)
        return np.array(resp['embedding'], dtype=np.float32)
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None


def split_into_chunks(text: str, file_path: str, file_title: str, window_size: int = 3, overlap: int = 1) -> List[SentenceWithSource]:
    sentences_with_source: List[SentenceWithSource] = []
    lines = text.split('\n')
    current_section = ""

    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        if line.startswith('#'):
            current_section = line.strip('#').strip()
            continue

        if '|' in line or line.startswith('---') or line.startswith('![]') or line.startswith('Fig.'):
            continue

        sents = nltk.sent_tokenize(line)
        for s in sents:
            s = s.strip()
            if len(s) > 20:
                sentences_with_source.append(
                    SentenceWithSource(
                        text=s,
                        file_path=file_path,
                        file_title=file_title,
                        line_number=line_num,
                        section_header=current_section,
                    )
                )
    # creating chunks w/ sliding windows
    chunks = []
    for i in range(0, len(sentences_with_source), window_size - overlap):
        window = sentences_with_source[i:i + window_size]
        if not window:
            continue

        # merge text of sentences in the window
        combined_text = " ".join(s.text for s in window)
        chunk = SentenceWithSource(
            text=combined_text,
            file_path=window[0].file_path,
            file_title=window[0].file_title,
            line_number=window[0].line_number,
            section_header=window[0].section_header,
        )
        chunks.append(chunk)

        # stop if we've reached the end
        if i + window_size >= len(sentences_with_source):
            break

    return chunks


def load_existing_data() -> Tuple[List[SentenceWithSource], Optional[np.ndarray], Optional[faiss.Index], Set[str]]:
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        embeddings = np.load(EMBEDDINGS_FILE) if EMBEDDINGS_FILE.exists() else None
        index = faiss.read_index(str(FAISS_INDEX_FILE)) if FAISS_INDEX_FILE.exists() else None

        sentences = [SentenceWithSource(**item) for item in metadata.get('sentences', [])]
        processed_files = set(metadata.get('processed_files', []))
        return sentences, embeddings, index, processed_files

    return [], None, None, set()


def save_data(sentences: List[SentenceWithSource], embeddings: np.ndarray, index: faiss.Index, processed_files: Set[str], model: str = "qwen3-embedding:0.6b"):
    np.save(EMBEDDINGS_FILE, embeddings)
    faiss.write_index(index, str(FAISS_INDEX_FILE))

    metadata = {
        'sentences': [asdict(s) for s in sentences],
        'processed_files': list(processed_files),
        'embedding_model': model,
        'dimension': int(embeddings.shape[1]) if embeddings is not None else 0,
        'total_sentences': len(sentences),
    }

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved {len(sentences)} sentences and updated FAISS index.")

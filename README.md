
# CRAG Document Reader — CRAG RAG Toolkit

This repository contains tools used to build a retrieval-augmented generation (RAG) system over the CRAG library (American Samoan coral reef research). The codebase focuses on extracting text and images from legacy reports and PDFs, preprocessing and chunking the content, creating embeddings, storing them in a vector store, and building a retriever + generation pipeline for question answering and summarization.

**This README now documents the current scripts, the end-to-end RAG build process, and quick usage examples.**

**Repository Snapshot:**
- **Files & artifacts:** [README.md](README.md), [extract_markdown.py](extract_markdown.py), [extract_metadata.py](extract_metadata.py), [describe_images.py](describe_images.py), [text_split.py](text_split.py), [semantic_retrieval_demo.py](semantic_retrieval_demo.py), `semantic_retrieval_demo.ipynb`, [summarize.py](summarize.py), [summaries.json](summaries.json), [image_descriptions.json](image_descriptions.json), [paper_metadata.json](paper_metadata.json), [requirements.txt](requirements.txt), [test_installation.py](test_installation.py), [test_torch.py](test_torch.py).
- **Data folders:** `output/` (source PDFs and processed outputs), `vector_store/` (persisted embeddings), `queries/` (e.g., `queries/coral_queries.json`).

**High-level goals:**
- Ingest historical CRAG PDFs and reports.
- Extract and normalize text and image metadata.
- Chunk and embed content for semantic search.
- Build a retriever that provides grounded context to an LLM for accurate answers and summaries about research findings and data.

**How the RAG system was built — step-by-step**

**1. Collection & organization**
- **Source files:** Place PDF reports and related files under `output/`. This repository contains many pre-collected reports from CRAG, organized by year and study in subfolders.

**2. Text and metadata extraction**
- **Script:** [extract_markdown.py](extract_markdown.py) (uses marker-pdf)
- **What it does:** Uses marker-pdf-based extraction to pull full document content (text, captions, embedded images and basic layout) into markdown and associated image files. This single-step extractor is the primary way we ingest the historical CRAG PDFs.
- **Supporting scripts:** [extract_metadata.py](extract_metadata.py) pulls bibliographic metadata into `paper_metadata.json` and [describe_images.py](describe_images.py) generates `image_descriptions.json` describing figures and plates detected in the extracted output.

**3. OCR and image preprocessing**
- **Tools used:** Tesseract (system dependency), `opencv-python`, and Pillow for cleaning and deskewing where necessary.
- **Why:** Many legacy reports are scans; preprocessing improves OCR accuracy. See `test_installation.py` to verify Tesseract and basic libs.

**4. Text cleaning & chunking**
- **Script:** [text_split.py](text_split.py)
- **Process:** Normalize whitespace, remove scanner artifacts, optionally keep figure captions with paragraphs. Split long pages into overlapping chunks (e.g., 500–1000 tokens with 50–200 token overlap) suitable for embedding and retrieval.

**5. Embeddings & vector store**
- **Vector store directory:** `vector_store/` — persisted embeddings and metadata.
- **Embedding options:** The project is model-agnostic; you can use OpenAI embeddings, Cohere, or local sentence-transformers (Hugging Face). The demo code supports swapping providers in `semantic_retrieval_demo.py`.
- **Typical flow:** For each chunk produced by `text_split.py`, create an embedding vector, and store the tuple (vector, chunk_text, source_id, page, chunk_index, metadata) in the vector store (FAISS, Chroma, or cloud services like Pinecone/Weaviate).

**6. Retriever & RAG pipeline**
- **Script / demo:** [semantic_retrieval_demo.py](semantic_retrieval_demo.py) and `semantic_retrieval_demo.ipynb`.
- **Pattern:** Given a question, the retriever finds the top-k semantically similar chunks. Those chunks are formatted into a context prompt (include citations: file and page) and sent with a user prompt to an LLM to generate grounded answers or summaries.
- **Prompt engineering:** Use short system instructions to ask the model to cite sources, prefer in-context evidence, and avoid hallucination. Optionally apply a reranker step to reorder retrieved chunks by exact-match signals.

**7. Post-processing, aggregation & outputs**
- **Summaries:** Use [summarize.py](summarize.py) to create consolidated summaries and store results in `summaries.json`.
- **Queries & benchmarks:** `queries/coral_queries.json` contains example queries used to validate retrieval quality.

**8. Iterate & evaluate**
- Run sample queries, inspect retrieved snippets and LLM answers, adjust chunk sizes, embedding model, and prompt templates.
- Store curated Q/A examples and adjust retrieval parameters (k, score threshold, reranker) as needed.

**Quick usage examples**

- **Install Python deps:**
```bash
pip install -r requirements.txt
```

- **Verify installation & Tesseract:**
```bash
python test_installation.py
```
(On macOS: `brew install tesseract` if not installed.)


- **Run metadata and markdown extraction (example):**
```bash
python extract_metadata.py --input output/1998_report/ --out-file paper_metadata.json
python extract_markdown.py --input output/1998_report/ --out-file extracted_markdown.md
```

- **Chunk text & build embeddings (example):**
```bash
python text_split.py --input extracted_markdown.md --chunks-dir chunks/
# then run your embedding pipeline over files in chunks/ and persist to vector_store/
```

- **Start the semantic retrieval demo:**
```bash
python semantic_retrieval_demo.py
```
Or open and run `semantic_retrieval_demo.ipynb` to interactively explore queries.

**Where outputs live**
- `vector_store/` — persisted embeddings and metadata for retrieval.
- `responses/` - responses that the model generated for queries
- `summaries.json`, `image_descriptions.json`, `paper_metadata.json` — processed artifacts produced by the pipeline.

**Notes & recommendations**
- Keep raw PDFs in `output/` and keep processed artifacts under distinct folders per document to simplify provenance.
- If using cloud embedding services, secure API keys via environment variables and do not commit them.
- For local setups, `sentence-transformers` is a good option to avoid API costs; FAISS is a fast local vector index.

---
Updated to reflect the current codebase and to document the step-by-step RAG build process for the CRAG corpus.
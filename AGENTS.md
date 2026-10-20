# Repository Guidelines

## Project Structure & Module Organization

This repository is a flat Python application for extracting and querying the CRAG coral-reef document collection. `chat.py` is the Streamlit UI, while `semantic_retrieval.py` and `vector_store_utils.py` implement retrieval and answer generation. Ingestion proceeds through `extract_markdown.py`, `extract_metadata.py`, `describe_images.py`, `text_split.py`, and `add_to_vector_store.py`; `add_all.py` batches paths from `all_filepaths.txt`.

Corpus-derived Markdown, metadata, and images live under `output/<document-name>/`. Query fixtures are in `queries/`, generated answers are in `responses/`, and aggregate artifacts include `paper_metadata.json`, `image_descriptions.json`, and `summaries.json`. Keep new reusable logic in focused modules rather than adding it to the UI.

## Build, Test, and Development Commands

Create an environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Run `streamlit run chat.py` for local development. Use `python extract_markdown.py` to process PDFs from `documents/`, `python text_split.py` to create sentence files, and `python add_to_vector_store.py path/to/file.md` to update FAISS data. `docker build -t crag-doc-reader .` builds the production image; run it with port `8501` exposed.

## Coding Style & Naming Conventions

Follow PEP 8 with four-space indentation. Use `snake_case` for functions and modules, `PascalCase` for dataclasses/Pydantic models, and uppercase names for module-level configuration. Add type hints and short docstrings to shared functions. Prefer `pathlib.Path`, UTF-8 file access, and explicit exception handling. No formatter or linter is configured, so keep imports grouped and review diffs for consistent formatting.

## Testing Guidelines

Run `python -m compileall *.py` and exercise the affected script with a small document or query. New deterministic logic should include `pytest` tests under `tests/`, named `test_<module>.py`; mock Ollama, OpenAI, and filesystem-heavy operations. Before declaring implementation complete, run Pyright on affected Python modules, compile the Python files, and run relevant pytest tests. Compilation does not check types. Fix errors introduced by the implementation, rerun affected checks, and report any pre-existing failures or unavailable checks. Mock external model calls during tests.

## Commit & Pull Request Guidelines

Recent commits use short, lowercase, action-oriented subjects such as `updated requirements.txt` and `implemented basic user auth`. Keep commits focused and avoid vague messages. Pull requests should describe the pipeline stage changed, commands run, required model/config updates, and generated-data impact. Link relevant issues and include screenshots for Streamlit UI changes.

## Security & Configuration

Keep `.env` and `config.yaml` untracked; never commit API keys, authentication cookies, or passwords. Ollama models and the vector-store path are environment-specific, so document any required local setup without checking in machine-specific secrets or large regenerated artifacts.

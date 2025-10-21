import ollama
from pathlib import Path
import json
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Configuration ---
MARKDOWN_FOLDER = Path("output")
METADATA_OUTPUT_FILE = Path("paper_metadata.json")
MODEL_TO_USE = 'qwen2.5:32b'  # Excellent for 16GB GPU - great at structured output
# ---------------------

# --- Pydantic Models ---
class Author(BaseModel):
    name: str
    department: Optional[str] = None
    institute: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

class PaperMetadata(BaseModel):
    title: str
    authors: List[Author]
    publication_venue: Optional[str] = Field(None, description="Journal, conference, or publisher")
    publication_year: Optional[int] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
# ---------------

EXTRACTION_PROMPT = """
You are a research assistant extracting metadata from scientific papers.
Analyze the following text from a scientific paper and extract the metadata.

Text:
"{text}"

Extract and return ONLY a valid JSON object with the following structure:
{{
  "title": "paper title",
  "authors": [
    {{
      "name": "author name",
      "department": "department if available",
      "institute": "institution if available",
      "city": "city if available",
      "country": "country if available"
    }}
  ],
  "publication_venue": "journal or conference name if available",
  "publication_year": year as integer if available,
  "doi": "DOI if available",
  "abstract": "abstract if available",
  "keywords": ["keyword1", "keyword2"] if available
}}

Return ONLY the JSON object, no other text.
"""

def load_existing_metadata():
    """Loads the metadata JSON file if it exists."""
    if METADATA_OUTPUT_FILE.exists():
        with open(METADATA_OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_metadata(metadata):
    """Saves the updated metadata dictionary to the JSON file."""
    with open(METADATA_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

def extract_metadata_from_markdown(md_path):
    """Reads markdown file and extracts first ~3000 chars for metadata extraction."""
    with open(md_path, 'r', encoding='utf-8') as f:
        # Read first portion of the file (usually contains title, authors, abstract)
        content = f.read(3000)
    return content

def main():
    if not MARKDOWN_FOLDER.exists():
        print(f"ERROR: Input folder '{MARKDOWN_FOLDER}' not found.")
        return

    # Find all markdown files in subdirectories
    md_files = list(MARKDOWN_FOLDER.glob("**/*.md"))
    if not md_files:
        print(f"No markdown files found in {MARKDOWN_FOLDER.resolve()}")
        return

    print(f"Found {len(md_files)} markdown files to process.")
    
    metadata_dict = load_existing_metadata()

    for md_path in md_files:
        # Get the PDF name from the markdown filename
        pdf_name = md_path.stem + ".pdf"
        
        if pdf_name in metadata_dict:
            print(f"⏭️  Skipping (already processed): {pdf_name}")
            continue

        print(f"\n--- Extracting metadata from: {pdf_name} ---")
        
        # Extract text from markdown
        text_sample = extract_metadata_from_markdown(md_path)
        
        # Retry logic: up to 5 attempts (1 initial + 4 retries)
        max_attempts = 5
        success = False
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Query LLM
                if attempt == 1:
                    print(f"  Querying {MODEL_TO_USE}...")
                else:
                    print(f"  Retry {attempt - 1}/{max_attempts - 1}...")
                    
                response = ollama.chat(
                    model=MODEL_TO_USE,
                    messages=[{'role': 'user', 'content': EXTRACTION_PROMPT.format(text=text_sample)}],
                    format='json'  # Request JSON format
                )
                
                # Parse response
                result_text = response['message']['content']
                result_json = json.loads(result_text)
                
                # Validate with Pydantic
                paper_meta = PaperMetadata(**result_json)
                
                # Hardcode pdf_name and store in dictionary
                metadata_entry = paper_meta.model_dump()
                metadata_entry['pdf_name'] = pdf_name
                metadata_dict[pdf_name] = metadata_entry
                save_metadata(metadata_dict)
                
                print(f"✅ Success: Extracted metadata for {pdf_name}")
                print(f"   Title: {paper_meta.title}")
                print(f"   Authors: {len(paper_meta.authors)}")
                
                success = True
                break
                
            except Exception as e:
                if attempt < max_attempts:
                    print(f"  ⚠️  Attempt {attempt} failed: {e}")
                else:
                    print(f"  ❌ ERROR processing {pdf_name} after {max_attempts} attempts: {e}")
        
        if not success:
            print(f"  Skipping {pdf_name} due to repeated failures.")

    print("\n--- All documents processed! ---")

if __name__ == "__main__":
    main()

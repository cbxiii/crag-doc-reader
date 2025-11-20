import ollama # pip install ollama
from pathlib import Path
import json
import re

# --- Configuration ---
# Folder with sentence-chunked text files from the previous script
SENTENCE_FOLDER = Path("chunked_sentences")
# The single JSON file where all summaries will be stored
SUMMARY_OUTPUT_FILE = Path("summaries.json")
# The local model to use for summarization
MODEL_TO_USE = 'llama3:8b'
# How many sentences to group into a single chunk for the "Map" step
SENTENCES_PER_CHUNK = 40 
# ---------------------

# --- Prompts ---
MAP_PROMPT = """
You are a research assistant specializing in scientific literature.
The following is a chunk of text from a larger document.
Your task is to write a concise summary of this specific chunk.
Focus on extracting the key findings, methods, and conclusions.

Text chunk:
"{text_chunk}"

Concise summary of the chunk:
"""

REDUCE_PROMPT = """
You are an expert synthesizer of scientific information.
The following are several summaries from different parts of a single document.
Your task is to combine these summaries into a single, cohesive, and comprehensive summary of the entire document.
Ensure the final summary is well-structured, easy to read, and captures the main points of the paper.
Return ONLY the comprehensive summary, without any introductory phrases or conversational text.

Summaries of document chunks:
"{text_chunk}"

Comprehensive summary:
"""
# ---------------

def load_existing_summaries():
    """Loads the summary JSON file if it exists."""
    if SUMMARY_OUTPUT_FILE.exists():
        with open(SUMMARY_OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_summaries(summaries):
    """Saves the updated summaries dictionary to the JSON file."""
    with open(SUMMARY_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, indent=2)

def get_sentences_from_file(file_path):
    """Reads a _sentences.txt file and returns a list of sentences."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Use regex to find all text following "--- SENTENCE # ---"
    sentences = re.findall(r'--- SENTENCE \d+ ---\n(.*?)(?=\n\n--- SENTENCE|\Z)', content, re.DOTALL)
    return [s.strip() for s in sentences]

def main():
    if not SENTENCE_FOLDER.exists():
        print(f"ERROR: Input folder '{SENTENCE_FOLDER}' not found.")
        return

    sentence_files = list(SENTENCE_FOLDER.glob("*_sentences.txt"))
    if not sentence_files:
        print(f"No sentence files found in {SENTENCE_FOLDER.resolve()}")
        return

    print(f"Found {len(sentence_files)} documents to summarize.")
    
    summaries = load_existing_summaries()

    for file_path in sentence_files:
        # Create a key for the JSON file from the original PDF name
        original_doc_name = file_path.name.replace("_sentences.txt", ".pdf")

        if original_doc_name in summaries:
            print(f"⏭️  Skipping (already summarized): {original_doc_name}")
            continue

        print(f"\n--- Summarizing: {original_doc_name} ---")
        
        sentences = get_sentences_from_file(file_path)
        if not sentences:
            print("  No sentences found in file.")
            continue

        # --- MAP STEP ---
        print(f"  Mapping {len(sentences)} sentences into chunks of {SENTENCES_PER_CHUNK}...")
        initial_summaries = []
        # Group sentences into larger chunks
        for i in range(0, len(sentences), SENTENCES_PER_CHUNK):
            chunk_text = " ".join(sentences[i:i + SENTENCES_PER_CHUNK])
            
            try:
                print(f"    - Summarizing chunk {i // SENTENCES_PER_CHUNK + 1}...")
                response = ollama.chat(
                    model=MODEL_TO_USE,
                    messages=[{'role': 'user', 'content': MAP_PROMPT.format(text_chunk=chunk_text)}]
                )
                initial_summaries.append(response['message']['content'])
            except Exception as e:
                print(f"    ❌ ERROR on chunk {i // SENTENCES_PER_CHUNK + 1}: {e}")

        # --- REDUCE STEP ---
        if not initial_summaries:
            print("  No initial summaries were generated. Cannot proceed to reduce step.")
            continue
            
        print("  Reducing initial summaries into a final summary...")
        combined_summaries_text = "\n\n---\n\n".join(initial_summaries)
        
        try:
            final_response = ollama.chat(
                model=MODEL_TO_USE,
                messages=[{'role': 'user', 'content': REDUCE_PROMPT.format(text_chunk=combined_summaries_text)}]
            )
            final_summary = final_response['message']['content']
            
            # --- SAVE STEP ---
            summaries[original_doc_name] = final_summary
            save_summaries(summaries)
            print(f"✅ Success: Saved final summary for {original_doc_name}")

        except Exception as e:
            print(f"  ❌ ERROR during final reduce step: {e}")

    print("\n--- All documents summarized! ---")

if __name__ == "__main__":
    main()

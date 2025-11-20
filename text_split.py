from pathlib import Path
import spacy # pip install spacy
            # python -m spacy download en_core_web_sm (download small English model)

# --- Configuration ---
MARKDOWN_FOLDER = Path("output") 
OUTPUT_SENTENCE_FOLDER = Path("chunked_sentences") # Folder for sentence output

# --- Load spaCy model ---
# Using the small model is usually sufficient and fast.
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading spaCy en_core_web_sm model...")
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# Increase max length if your paragraphs are very long (default is 1 million chars)
nlp.max_length = 10_000_000 

def main():
    OUTPUT_SENTENCE_FOLDER.mkdir(parents=True, exist_ok=True)
    
    md_files = list(MARKDOWN_FOLDER.glob("**/*.md"))
    
    if not md_files:
        print(f"No Markdown files found in {MARKDOWN_FOLDER.resolve()}")
        return

    print(f"Found {len(md_files)} Markdown files to sentence chunk.")

    for md_path in md_files:
        # Define the expected output path first
        output_filename = f"{md_path.stem}_sentences.txt"
        output_txt_path = OUTPUT_SENTENCE_FOLDER / output_filename

        # --- START ADDED CODE ---
        # Check if the output file already exists before processing
        if output_txt_path.exists():
            print(f"⏭️  Skipping (already processed): {md_path.name}")
            continue # Move to the next file in the loop
        # --- END ADDED CODE ---

        print(f"\n--- Sentence Chunking: {md_path.name} ---")
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                markdown_text = f.read()
                
            # --- spaCy Sentence Splitting ---
            # Process the text with spaCy
            doc = nlp(markdown_text) 
            
            # Extract sentences as strings
            sentences = [sent.text.strip() for sent in doc.sents]
            # -----------------------------
            
            # Filter out very short "sentences" that might just be formatting artifacts
            sentences = [s for s in sentences if len(s.split()) > 3] # Keep if more than 3 words
            
            with open(output_txt_path, "w", encoding="utf-8") as outfile:
                for i, sentence in enumerate(sentences):
                    outfile.write(f"--- SENTENCE {i+1} ---\n")
                    outfile.write(sentence) 
                    outfile.write("\n\n") 
                    
            print(f"✅ Success: Saved {len(sentences)} sentences to {output_txt_path}")

        except FileNotFoundError:
            print(f"❌ ERROR: Could not find file {md_path}")
        except Exception as e:
            print(f"❌ ERROR processing {md_path.name}: {e}")

    print("\n--- All Markdown files sentence chunked! ---")

if __name__ == "__main__":
    main()
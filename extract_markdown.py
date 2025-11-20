import subprocess
from pathlib import Path

INPUT_FOLDER = Path("documents")
OUTPUT_FOLDER = Path("output")

def main():
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    
    # Find all PDF files recursively in the input folder
    pdf_files = list(INPUT_FOLDER.glob("**/*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {INPUT_FOLDER.resolve()}")
        return

    print(f"Found {len(pdf_files)} PDFs to process. Output will be saved in {OUTPUT_FOLDER.resolve()}")

    for pdf_path in pdf_files:
        pdf_name_stem = pdf_path.stem  # Gets the filename without .pdf
        
        # Define the correct output path that marker WILL create
        # (e.g., output/STEM/STEM.md)
        expected_output_dir = OUTPUT_FOLDER / pdf_name_stem
        expected_md_file = expected_output_dir / f"{pdf_name_stem}.md"

        # Check if that file already exists
        if expected_md_file.exists():
            print(f"⏭️  Skipping (already processed): {pdf_path.name}")
            continue
            
        command = [
            "marker_single",
            str(pdf_path.resolve()),        # Full path to the input PDF
            "--output_dir",                 # The named option for the output dir
            str(OUTPUT_FOLDER.resolve())    # Full path to the *main* output folder
        ]
        
        print(f"\n--- Processing: {pdf_path.name} ---")
        
        try:
            # Run the command
            # Marker will auto-detect your GPU if PyTorch is set up correctly.
            subprocess.run(command, check=True)
            print(f"✅ Success: Output for {pdf_path.name} is in {expected_output_dir}")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ ERROR processing {pdf_path.name}: {e}")
        except FileNotFoundError:
            print("❌ ERROR: 'marker_single' command not found.")
            print("   Please make sure your virtual environment is active ('marker-env\\Scripts\\activate')")
            break # Stop the script if marker isn't installed/found
        except KeyboardInterrupt:
            print("\n🛑 User interrupted process. Exiting.")
            break

    print("\n--- All PDFs processed! ---")

if __name__ == "__main__":
    main()
import ollama
from pathlib import Path
import json
import re
from pydantic import BaseModel, Field
from typing import Optional, Tuple, List

# --- Configuration ---
OUTPUT_FOLDER = Path("output")
DESCRIPTIONS_FILE = Path("image_descriptions.json")
MODEL_TO_USE = 'llava:13b'
# ---------------------

# --- Pydantic Model ---
class ImageDescription(BaseModel):
    pdf_name: str = Field(description="Name of the PDF this image comes from")
    image_path: str = Field(description="Path to the image file")
    context_before: str = Field(description="2 sentences before the image")
    context_after: str = Field(description="2 sentences after the image")
    description: str = Field(description="LLM-generated description of the image")
# ---------------

DESCRIPTION_PROMPT = """
You are analyzing a scientific figure from a research paper.

Context before the figure:
{context_before}

Context after the figure:
{context_after}

Please provide a detailed description of this image, including:
- What type of figure it is (graph, map, diagram, photograph, etc.)
- Key visual elements and features
- What scientific information it conveys
- How it relates to the surrounding text context

Description:
"""

def load_existing_descriptions():
    """Loads the image descriptions JSON file if it exists."""
    if DESCRIPTIONS_FILE.exists():
        with open(DESCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_descriptions(descriptions):
    """Saves the updated descriptions dictionary to the JSON file."""
    with open(DESCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(descriptions, f, indent=2)

def find_image_context_in_markdown(markdown_file: Path, image_filename: str) -> Tuple[Optional[str], Optional[str]]:
    """Find the context before and after an image reference in a markdown file.
    
    Returns:
        (context_before, context_after) or (None, None) if not found
    """
    if not markdown_file.exists():
        return None, None
    
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for markdown image reference: ![](image_filename)
    pattern = rf'!\[\]\({re.escape(image_filename)}\)'
    match = re.search(pattern, content)
    
    if not match:
        return None, None
    
    # Find the position of the image reference
    image_pos = match.start()
    
    # Split content into lines to get context
    lines = content[:image_pos].split('\n')
    lines_after = content[match.end():].split('\n')
    
    # Get the last non-empty paragraph before the image (up to 3 lines)
    context_before_lines = []
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith('#'):  # Skip headers
            context_before_lines.insert(0, line)
            if len(context_before_lines) >= 3:
                break
        elif context_before_lines:  # Stop at empty line after we have some content
            break
    
    # Get the first non-empty paragraph after the image (up to 3 lines)
    context_after_lines = []
    for line in lines_after:
        line = line.strip()
        if line and not line.startswith('#'):  # Skip headers
            context_after_lines.append(line)
            if len(context_after_lines) >= 3:
                break
        elif context_after_lines:  # Stop at empty line after we have some content
            break
    
    context_before = ' '.join(context_before_lines)
    context_after = ' '.join(context_after_lines)
    
    return context_before, context_after

def describe_image(image_path, context_before, context_after):
    """Uses llava model to describe an image with context."""
    prompt = DESCRIPTION_PROMPT.format(
        context_before=context_before,
        context_after=context_after
    )
    
    response = ollama.chat(
        model=MODEL_TO_USE,
        messages=[{
            'role': 'user',
            'content': prompt,
            'images': [str(image_path)]
        }]
    )
    
    return response['message']['content']

def main():
    if not OUTPUT_FOLDER.exists():
        print(f"ERROR: Output folder '{OUTPUT_FOLDER}' not found.")
        return

    # Find all image files in output subdirectories
    image_files = []
    for ext in ['*.jpeg', '*.jpg', '*.png']:
        image_files.extend(OUTPUT_FOLDER.glob(f"**/{ext}"))
    
    if not image_files:
        print(f"No image files found in {OUTPUT_FOLDER.resolve()}")
        return

    print(f"Found {len(image_files)} image files to process.")
    
    descriptions_dict = load_existing_descriptions()

    for image_path in image_files:
        image_key = str(image_path.relative_to(OUTPUT_FOLDER))
        
        if image_key in descriptions_dict:
            print(f"⏭️  Skipping (already processed): {image_key}")
            continue

        print(f"\n--- Processing: {image_key} ---")
        
        try:
            # Find corresponding markdown file
            # Images are in subdirectories named after the PDF (without .pdf extension)
            pdf_dir_name = image_path.parent.name
            pdf_name = pdf_dir_name + ".pdf"
            markdown_file = image_path.parent / f"{pdf_dir_name}.md"
            
            # Find context in markdown file
            context_before, context_after = find_image_context_in_markdown(markdown_file, image_path.name)
            
            if context_before is None:
                print(f"  ⚠️  Warning: Image reference not found in markdown file: {markdown_file.name}")
                context_before = ""
                context_after = ""
            else:
                print(f"  ✓ Found image reference in {markdown_file.name}")
            
            # Describe image using llava
            print(f"  Querying {MODEL_TO_USE}...")
            description = describe_image(image_path, context_before, context_after)
            
            # Create ImageDescription object
            img_desc = ImageDescription(
                pdf_name=pdf_name,
                image_path=image_key,
                context_before=context_before,
                context_after=context_after,
                description=description
            )
            
            # Store in dictionary
            descriptions_dict[image_key] = img_desc.model_dump()
            save_descriptions(descriptions_dict)
            
            print(f"✅ Success: Described {image_key}")
            
        except Exception as e:
            print(f"  ❌ ERROR processing {image_key}: {e}")

    print("\n--- All images processed! ---")

if __name__ == "__main__":
    main()

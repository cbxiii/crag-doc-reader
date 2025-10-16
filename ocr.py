"""
Script to run Optical Character Recognition on research paper PDFs.
"""

import pandas as pd
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from pdfminer.high_level import extract_text
from PIL import Image
from pathlib import Path

def extract_text_from_pdf(filepath):
    try:
        text = extract_text(filepath)
        if text and len(text) > 200:
            return text
    except Exception:
        print(Exception)
        text = ""
    
    # convert pdf to list of images
    images = convert_from_path(filepath, dpi=300)
    pages = []

    # extract text from images
    for i, image in enumerate(images):
        page_text = pytesseract.image_to_string(images[i], lang='eng')
        pages.append(page_text)
    
    return "\n\n".join(pages)
    
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ocr.py path/to/file.pdf [out.txt]")
    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "output.txt"
    txt = extract_text_from_pdf(pdf)
    Path(out).write_text(txt, encoding='utf-8') # type: ignore
    print(f"Wrote to {out} (chars: {len(txt)})") # type: ignore
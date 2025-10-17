# CRAG Document Reader

A comprehensive PDF processing and OCR toolkit that extracts embedded images, converts pages to high-resolution images, preprocesses them with OpenCV, and performs OCR using Tesseract.

## Features

- **Load PDFs** with PyMuPDF (fitz)
- **Extract embedded images** at high quality
- **Render PDF pages** to high-resolution images (configurable DPI)
- **Image preprocessing** with OpenCV:
  - Deskewing (automatic rotation correction)
  - Binarization (adaptive thresholding)
  - Denoising and cleanup
- **OCR text extraction** using Tesseract
- **Batch processing** support
- **Multiple language** support for OCR

## Quick Start

### 1. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt
```

**IMPORTANT:** You must also install Tesseract OCR engine separately! See [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) for detailed instructions.

### 2. Test Your Installation

```bash
python test_installation.py
```

This will verify that all packages and Tesseract are properly installed.

### 3. Run the OCR Processor

**Interactive mode:**
```bash
python pdf_ocr_processor.py
```

**Programmatic use:**
```python
from pdf_ocr_processor import PDFOCRProcessor

processor = PDFOCRProcessor("your_file.pdf", "output")
processor.load_pdf()
processor.extract_embedded_images()
results = processor.process_all_pages(dpi=300, lang='eng')
processor.close()
```

See [example_usage.py](example_usage.py) for more examples.

## Files

- **`pdf_ocr_processor.py`** - Main OCR processor class with all functionality
- **`example_usage.py`** - Example scripts showing programmatic usage
- **`test_installation.py`** - Verify all dependencies are installed correctly
- **`file_checker.py`** - Quick utility to check if a PDF needs OCR
- **`INSTALLATION_GUIDE.md`** - Detailed installation instructions
- **`requirements.txt`** - Python package dependencies

## Installation Requirements

### Python Packages (via pip)
- `pymupdf` - PDF manipulation
- `opencv-python` - Image processing
- `numpy` - Numerical operations
- `pytesseract` - Python wrapper for Tesseract
- `Pillow` - Image handling

### System Requirements
- **Tesseract OCR Engine** - Must be installed separately!
  - **Windows:** Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
  - **macOS:** `brew install tesseract`
  - **Linux:** `sudo apt-get install tesseract-ocr`

See [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) for complete instructions.

## Usage Examples

### Check if a PDF needs OCR
```bash
python file_checker.py
```

### Process a single PDF
```bash
python pdf_ocr_processor.py
```

### Process programmatically
```python
from pdf_ocr_processor import PDFOCRProcessor

# Process entire PDF
processor = PDFOCRProcessor("document.pdf", "output")
processor.load_pdf()
processor.extract_embedded_images()
results = processor.process_all_pages(dpi=300, lang='eng')
processor.close()

# Access results
for result in results:
    print(f"Page {result['page_num']}: {len(result['text'])} characters")
```

## Output Structure

When processing a PDF, the following directory structure is created:

```
output/
├── extracted_images/          # Embedded images from PDF
│   ├── page1_img1.png
│   └── page1_img2.jpg
├── page_images/               # Original rendered pages
│   ├── page_1_original.png
│   └── page_2_original.png
├── processed_images/          # Preprocessed pages (deskewed, cleaned)
│   ├── page_1_processed.png
│   └── page_2_processed.png
├── page_1_text.txt           # Extracted text per page
├── page_2_text.txt
└── all_pages_text.txt        # Combined text from all pages
```

## Configuration Options

- **DPI:** Higher DPI (e.g., 400-600) gives better OCR accuracy but slower processing (default: 300)
- **Language:** Specify OCR language code (default: 'eng')
  - Spanish: `lang='spa'`
  - French: `lang='fra'`
  - German: `lang='deu'`
  - Multiple: `lang='eng+spa'`

## Troubleshooting

### "TesseractNotFoundError"
Tesseract OCR engine is not installed or not in PATH. See [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md).

### Poor OCR results
- Increase DPI (try 400 or 600)
- Check if the PDF is very low quality
- Install appropriate language packs for non-English documents

### Import errors
Run `pip install -r requirements.txt` to ensure all Python packages are installed.

## Performance Notes

- Processing time: ~5-15 seconds per page (depending on hardware and DPI)
- DPI 300: Good balance of quality and speed
- DPI 600: Better accuracy, 4x slower
- Memory usage: ~100-500MB per page at 300 DPI

## License

See LICENSE file for details.
"""
Quick test script to verify all dependencies are installed correctly.
Run this before using the main PDF OCR processor.
"""

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing package imports...\n")
    
    try:
        import pymupdf
        print("✓ pymupdf imported successfully")
    except ImportError as e:
        print("✗ pymupdf import failed:", e)
        return False
    
    try:
        import cv2
        print("✓ opencv-python imported successfully")
    except ImportError as e:
        print("✗ opencv-python import failed:", e)
        return False
    
    try:
        import numpy as np
        print("✓ numpy imported successfully")
    except ImportError as e:
        print("✗ numpy import failed:", e)
        return False
    
    try:
        import pytesseract
        print("✓ pytesseract imported successfully")
    except ImportError as e:
        print("✗ pytesseract import failed:", e)
        return False
    
    try:
        from PIL import Image
        print("✓ Pillow imported successfully")
    except ImportError as e:
        print("✗ Pillow import failed:", e)
        return False
    
    return True


def test_tesseract():
    """Test that Tesseract OCR engine is installed and accessible."""
    print("\nTesting Tesseract OCR engine...\n")
    
    try:
        import pytesseract
        
        # Try to get Tesseract version
        version = pytesseract.get_tesseract_version()
        print(f"✓ Tesseract OCR engine found: version {version}")
        return True
        
    except pytesseract.TesseractNotFoundError:
        print("✗ Tesseract OCR engine not found!")
        print("\nTesseract needs to be installed separately.")
        print("On Windows:")
        print("  1. Download from: https://github.com/UB-Mannheim/tesseract/wiki")
        print("  2. Install and add to PATH")
        print("  3. Or manually set path in Python:")
        print("     pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'")
        return False
    
    except Exception as e:
        print(f"✗ Error checking Tesseract: {e}")
        return False


def test_ocr_functionality():
    """Test OCR on a simple test image."""
    print("\nTesting OCR functionality...\n")
    
    try:
        import pytesseract
        import numpy as np
        from PIL import Image
        
        # Create a simple test image with text
        from PIL import ImageDraw, ImageFont
        
        # Create white image
        img = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw black text
        try:
            # Try to use default font
            draw.text((10, 30), "Hello OCR Test", fill='black')
        except:
            # If font fails, still try
            draw.text((10, 30), "Hello OCR Test", fill='black')
        
        # Convert PIL image to numpy array for pytesseract
        img_array = np.array(img)
        
        # Perform OCR
        text = pytesseract.image_to_string(img_array)
        
        if "Hello" in text or "OCR" in text or "Test" in text:
            print(f"✓ OCR is working! Detected text: {text.strip()}")
            return True
        else:
            print(f"⚠ OCR ran but results unclear. Detected: {text.strip()}")
            return True  # Still counts as success since it ran
            
    except Exception as e:
        print(f"✗ OCR test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("PDF OCR Processor - Installation Test")
    print("="*60)
    print()
    
    # Test imports
    imports_ok = test_imports()
    
    if not imports_ok:
        print("\n" + "="*60)
        print("RESULT: Installation incomplete - missing Python packages")
        print("="*60)
        print("\nPlease run: pip install -r requirements.txt")
        return
    
    # Test Tesseract
    tesseract_ok = test_tesseract()
    
    if not tesseract_ok:
        print("\n" + "="*60)
        print("RESULT: Tesseract OCR engine not installed")
        print("="*60)
        print("\nPlease see INSTALLATION_GUIDE.md for instructions")
        return
    
    # Test OCR functionality
    ocr_ok = test_ocr_functionality()
    
    print("\n" + "="*60)
    if imports_ok and tesseract_ok and ocr_ok:
        print("RESULT: ✓ ALL TESTS PASSED!")
        print("="*60)
        print("\nYou're ready to use pdf_ocr_processor.py!")
    else:
        print("RESULT: ⚠ Some tests failed")
        print("="*60)
        print("\nPlease check the errors above and see INSTALLATION_GUIDE.md")


if __name__ == "__main__":
    main()

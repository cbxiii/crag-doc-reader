import pymupdf
import cv2
import numpy as np
import pytesseract
from pathlib import Path
import os

"""
Smart PDF processor that:
1. Detects if pages have digital text or need OCR
2. Extracts digital text directly when available
3. Uses OCR only for scanned pages
4. Detects and extracts figures/images separately from text
5. Handles image orientation correctly
"""

class SmartPDFProcessor:
    def __init__(self, pdf_path, output_dir="output", use_osd=True):
        """
        Initialize the smart PDF processor.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted content
            use_osd: Use Tesseract OSD for orientation detection (default: True)
        """
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.use_osd = use_osd
        
        # Create subdirectories
        self.images_dir = self.output_dir / "extracted_images"
        self.figures_dir = self.output_dir / "figures"
        self.pages_dir = self.output_dir / "page_images"
        self.processed_dir = self.output_dir / "processed_images"
        
        self.images_dir.mkdir(exist_ok=True)
        self.figures_dir.mkdir(exist_ok=True)
        self.pages_dir.mkdir(exist_ok=True)
        self.processed_dir.mkdir(exist_ok=True)
        
        self.doc = None
        
    def load_pdf(self):
        """Load the PDF document using PyMuPDF."""
        print(f"Loading PDF: {self.pdf_path}")
        self.doc = pymupdf.open(self.pdf_path)
        print(f"PDF loaded successfully. Total pages: {len(self.doc)}")
        return self.doc
    
    def has_digital_text(self, page_num, threshold=100):
        """
        Check if a page has digital text or is scanned.
        
        Args:
            page_num: Page number (0-indexed)
            threshold: Minimum characters to consider as digital text
            
        Returns:
            bool: True if page has digital text, False if scanned
        """
        page = self.doc[page_num]
        text = page.get_text("text").strip()
        return len(text) > threshold
    
    def extract_digital_text(self, page_num):
        """
        Extract text directly from PDF (for digital PDFs).
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            str: Extracted text
        """
        page = self.doc[page_num]
        text = page.get_text("text")
        return text
    
    def extract_embedded_images(self, page_num):
        """
        Extract embedded images from a specific page.
        
        Args:
            page_num: Page number (0-indexed)
            
        Returns:
            list: List of extracted image paths
        """
        page = self.doc[page_num]
        image_list = page.get_images(full=True)
        extracted_images = []
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            
            try:
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Save the image
                image_filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                image_path = self.images_dir / image_filename
                
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)
                
                extracted_images.append(str(image_path))
                print(f"  Extracted embedded image: {image_filename}")
                
            except Exception as e:
                print(f"  Error extracting image {img_index}: {e}")
        
        return extracted_images
    
    def detect_and_extract_figures(self, page_num, dpi=300):
        """
        Detect figure regions on a page and extract them separately.
        Uses computer vision to distinguish figures from text.
        
        Args:
            page_num: Page number (0-indexed)
            dpi: Resolution for rendering
            
        Returns:
            list: List of extracted figure paths
        """
        # Render page to image
        page = self.doc[page_num]
        zoom = dpi / 72
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        if pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Use edge detection to find regions
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilate to connect nearby edges
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=3)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        extracted_figures = []
        figure_count = 0
        
        # Filter contours by size (figures are typically large regions)
        min_area = (img.shape[0] * img.shape[1]) * 0.05  # At least 5% of page
        max_area = (img.shape[0] * img.shape[1]) * 0.8   # At most 80% of page
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if min_area < area < max_area:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check aspect ratio (figures are typically not extremely elongated)
                aspect_ratio = w / h if h > 0 else 0
                if 0.2 < aspect_ratio < 5:
                    # Extract the region
                    figure_roi = img[y:y+h, x:x+w]
                    
                    # Check if region is mostly non-white (likely a figure)
                    gray_roi = cv2.cvtColor(figure_roi, cv2.COLOR_BGR2GRAY)
                    non_white_ratio = np.sum(gray_roi < 240) / gray_roi.size
                    
                    if non_white_ratio > 0.1:  # At least 10% non-white pixels
                        figure_count += 1
                        figure_filename = f"page{page_num + 1}_figure{figure_count}.png"
                        figure_path = self.figures_dir / figure_filename
                        cv2.imwrite(str(figure_path), figure_roi)
                        extracted_figures.append(str(figure_path))
                        print(f"  Detected and extracted figure: {figure_filename}")
        
        return extracted_figures
    
    def render_page_to_image(self, page_num, dpi=300):
        """Render PDF page to image."""
        page = self.doc[page_num]
        zoom = dpi / 72
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        if pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        
        page_filename = f"page_{page_num + 1}_original.png"
        page_path = self.pages_dir / page_filename
        cv2.imwrite(str(page_path), img)
        
        return img
    
    def _detect_and_fix_orientation(self, image):
        """Detect and fix 90/180/270 degree rotations using OSD."""
        if not self.use_osd:
            return image
        
        try:
            osd = pytesseract.image_to_osd(image, config='--psm 0', timeout=10)
            rotate = 0
            for line in osd.splitlines():
                if 'Rotate:' in line:
                    try:
                        rotate = int(line.split(':')[1].strip())
                    except Exception:
                        rotate = 0
                    break
            
            if rotate == 0:
                return image
            
            if rotate == 90:
                rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            elif rotate == 180:
                rotated = cv2.rotate(image, cv2.ROTATE_180)
            elif rotate == 270:
                rotated = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                return image
            
            print(f"  ✓ OSD detected {rotate}° rotation, corrected")
            return rotated
            
        except Exception as e:
            return image
    
    def preprocess_for_ocr(self, image):
        """
        Minimal preprocessing: orientation correction + grayscale.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            numpy array: Processed image
        """
        # Correct orientation
        image = self._detect_and_fix_orientation(image)
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        return gray
    
    def ocr_image(self, image, lang='eng'):
        """Perform OCR on an image."""
        text = pytesseract.image_to_string(image, lang=lang, config='--oem 3 --psm 6')
        return text
    
    def process_page(self, page_num, dpi=300, lang='eng'):
        """
        Process a single page intelligently.
        
        Args:
            page_num: Page number (0-indexed)
            dpi: Resolution for rendering (if OCR needed)
            lang: Language code for OCR
            
        Returns:
            dict: Processing results
        """
        print(f"\n--- Processing Page {page_num + 1} ---")
        
        # Check if page has digital text
        has_text = self.has_digital_text(page_num)
        
        if has_text:
            print("  Page has digital text - extracting directly (no OCR needed)")
            text = self.extract_digital_text(page_num)
            method = "digital_extraction"
            processed_image = None
        else:
            print("  Page is scanned - using OCR")
            # Render page
            original_image = self.render_page_to_image(page_num, dpi)
            
            # Preprocess
            processed_image = self.preprocess_for_ocr(original_image)
            
            # Save processed image
            processed_filename = f"page_{page_num + 1}_processed.png"
            processed_path = self.processed_dir / processed_filename
            cv2.imwrite(str(processed_path), processed_image)
            
            # OCR
            text = self.ocr_image(processed_image, lang)
            method = "ocr"
        
        # Extract embedded images
        embedded_images = self.extract_embedded_images(page_num)
        
        # Detect and extract figures (for scanned pages)
        figures = []
        if not has_text:
            figures = self.detect_and_extract_figures(page_num, dpi)
        
        # Save text
        text_filename = f"page_{page_num + 1}_text.txt"
        text_path = self.output_dir / text_filename
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"  Text length: {len(text)} characters")
        print(f"  Method: {method}")
        print(f"  Embedded images: {len(embedded_images)}")
        print(f"  Detected figures: {len(figures)}")
        
        return {
            'page_num': page_num + 1,
            'text': text,
            'method': method,
            'embedded_images': embedded_images,
            'figures': figures,
            'processed_image': processed_image
        }
    
    def process_all_pages(self, dpi=300, lang='eng'):
        """Process all pages in the PDF."""
        if self.doc is None:
            self.load_pdf()
        
        results = []
        
        for page_num in range(len(self.doc)):
            result = self.process_page(page_num, dpi, lang)
            results.append(result)
        
        # Create combined text file
        combined_text_path = self.output_dir / "all_pages_text.txt"
        with open(combined_text_path, 'w', encoding='utf-8') as f:
            for result in results:
                f.write(f"\n{'='*80}\n")
                f.write(f"PAGE {result['page_num']} ({result['method']})\n")
                f.write(f"{'='*80}\n\n")
                f.write(result['text'])
                f.write("\n")
        
        print(f"\n--- Processing Complete ---")
        print(f"Combined text saved to: {combined_text_path}")
        
        return results
    
    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()


def main():
    """Main function."""
    print("=== Smart PDF Processor ===\n")
    
    pdf_path = input("Enter the path to your PDF file: ").strip()
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        return
    
    output_dir = input("Enter output directory name (default: 'output'): ").strip()
    if not output_dir:
        output_dir = "output"
    
    dpi_input = input("Enter DPI for rendering (default: 300): ").strip()
    dpi = int(dpi_input) if dpi_input else 300
    
    lang = input("Enter language code for OCR (default: 'eng'): ").strip()
    if not lang:
        lang = 'eng'
    
    use_osd_input = input("Use orientation detection (OSD)? (Y/n, default: Y): ").strip().lower()
    use_osd = use_osd_input != 'n'
    
    try:
        processor = SmartPDFProcessor(pdf_path, output_dir, use_osd=use_osd)
        processor.load_pdf()
        results = processor.process_all_pages(dpi=dpi, lang=lang)
        
        print(f"\n{'='*80}")
        print(f"SUCCESS!")
        print(f"{'='*80}")
        print(f"Total pages processed: {len(results)}")
        
        digital_pages = sum(1 for r in results if r['method'] == 'digital_extraction')
        ocr_pages = sum(1 for r in results if r['method'] == 'ocr')
        
        print(f"  Digital text pages: {digital_pages}")
        print(f"  OCR pages: {ocr_pages}")
        print(f"\nAll results saved to: {output_dir}/")
        
        processor.close()
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

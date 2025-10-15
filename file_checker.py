import pymupdf

"""
Little script that checks if a document contains digital text
or is a scanned image that needs OCR.
"""

def file_checker(file_path):
    doc = pymupdf.open(file_path)
    page = doc[0]
    text = page.get_text("text")
    if len(text) > 100:
        print("pdf likely contains digital text (no OCR needed)")
        print(len(text))
        print(text)
    else:
        print("pdf likely scanned (OCR needed)")
        print(len(text))
        print(text)

# document file path should be "documents/[filename]"
chosen_file = input("Please paste file you want to check (file path should start with 'documents/'): ")
print()
file_checker(chosen_file)
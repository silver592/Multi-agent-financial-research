#services/parser.py --> This file is responsible for parsing the PDF. It uses PyMuPDF to open the PDF and extract text from each page

from pypdf import PdfReader


def parse_pdf(file_path):
    """
    Extract text from every PDF page while preserving page numbers.
    """

    reader = PdfReader(file_path)

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):

        text = page.extract_text()

        if text:
            pages.append({
                "page_number": page_number,
                "text": text.strip()
            })

    return pages
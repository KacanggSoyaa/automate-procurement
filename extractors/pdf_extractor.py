import os
import fnmatch
import pdfplumber
from pathlib import Path
from typing import Dict, List

class PDFExtractor:
    def __init__(self, engine: str = "pdfplumber"):
        self.engine = engine

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text.append(extracted)
        return "\n".join(text)

    def extract_itb_folder(self, itb_dir: str, pattern: str = '*.pdf') -> List[Dict]:
        results = []
        for fname in os.listdir(itb_dir):
            if fname.lower().endswith('.pdf') and fnmatch.fnmatch(fname, pattern):
                path = os.path.join(itb_dir, fname)
                try:
                    content = self.extract_text_from_pdf(path)
                    results.append({
                        'filename': fname,
                        'path': path,
                        'content': content,
                        'size': len(content)
                    })
                except Exception as e:
                    results.append({
                        'filename': fname,
                        'path': path,
                        'error': str(e),
                        'content': ''
                    })
        return results

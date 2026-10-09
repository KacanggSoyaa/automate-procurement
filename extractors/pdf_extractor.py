"""PDF text and image extraction utilities for ITB packages."""
import os
import fnmatch
from pathlib import Path
from typing import Dict, List

# PyMuPDF is the primary engine (fast); pdfplumber is a pure-Python fallback.
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# Extensions treated as standalone images (screenshots) inside an ITB folder.
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff')


class PDFExtractor:
    """Reads text out of PDFs and finds images/screenshots in a folder."""

    def __init__(self, engine: str = "pymupdf"):
        """Store the preferred engine name (PyMuPDF, with pdfplumber fallback)."""
        self.engine = engine

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Return the concatenated text of every page in a single PDF.

        Uses PyMuPDF when available because it is far faster than pdfplumber;
        falls back to pdfplumber only if PyMuPDF is missing.
        """
        if fitz is not None:
            doc = fitz.open(pdf_path)
            try:
                return "\n".join(page.get_text() for page in doc)
            finally:
                doc.close()

        if pdfplumber is None:
            raise RuntimeError(
                "No PDF engine available. Install pymupdf (preferred) or pdfplumber."
            )
        text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text.append(extracted)
        return "\n".join(text)

    def extract_itb_folder(self, itb_dir: str, pattern: str = '*.pdf') -> List[Dict]:
        """Read every PDF in a folder that matches a filename glob.

        Returns one dict per file with keys ``filename``, ``path``, ``content``
        and ``size``; unreadable files carry an ``error`` key and empty content.
        """
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

    def render_image_pages(self, pdf_path: str, out_dir: str, dpi: int = 150, min_text: int = 50) -> List[str]:
        """Render PDF pages that contain images or almost no text (scanned/image-only pages)."""
        if fitz is None:
            return []
        out_paths = []
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        doc = fitz.open(pdf_path)
        try:
            for i, page in enumerate(doc):
                text = page.get_text().strip()
                has_images = len(page.get_images(full=True)) > 0
                if has_images or len(text) < min_text:
                    pix = page.get_pixmap(dpi=dpi)
                    out = Path(out_dir) / f"{Path(pdf_path).stem}_p{i + 1}.png"
                    pix.save(str(out))
                    out_paths.append(str(out))
        finally:
            doc.close()
        return out_paths

    def collect_image_files(self, folder: str, patterns: List[str] = None) -> List[str]:
        """Collect standalone image files (e.g. screenshots) from a folder."""
        patterns = patterns or ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.bmp']
        found = []
        for fname in os.listdir(folder):
            if fname.lower().endswith(IMAGE_EXTENSIONS) and any(
                fnmatch.fnmatch(fname, p) for p in patterns
            ):
                found.append(os.path.join(folder, fname))
        return sorted(found)

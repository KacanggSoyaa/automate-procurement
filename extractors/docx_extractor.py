from docx import Document

class DocxExtractor:
    def extract_text(self, docx_path: str) -> str:
        doc = Document(docx_path)
        lines = []
        for para in doc.paragraphs:
            lines.append(para.text)
        return "\n".join(lines)

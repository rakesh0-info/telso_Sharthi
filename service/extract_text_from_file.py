import pypdf
from docx import Document

def extract_text_from_file(file_path: str, file_extension: str) -> str:
    """Extracts text content safely from PDF, DOCX, or TXT files."""
    extracted_text = ""
    try:
        if file_extension == ".txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                extracted_text = f.read()
        elif file_extension == ".pdf":
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        elif file_extension == ".docx":
            doc = Document(file_path)
            for para in doc.paragraphs:
                if para.text:
                    extracted_text += para.text + "\n"
    except Exception as e:
        print(f"[Extraction Warning] Failed to parse text from file: {str(e)}")
    
    # Truncate text to a safe token threshold (e.g., first 15,000 characters) to prevent context exhaustion
    return extracted_text[:15000].strip()
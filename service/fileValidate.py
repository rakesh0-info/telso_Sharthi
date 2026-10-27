import os
import uuid
import filetype
from fastapi import UploadFile, HTTPException, status

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt"
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_DIR = "secure_uploads/quizzes"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def validate_and_save_file(file: UploadFile) -> str:
    # 1. Read first 2048 bytes to inspect magic headers
    header_chunk = file.file.read(2048)
    file.file.seek(0)  # Reset pointer to beginning

    # 2. Detect actual file type from binary content
    kind = filetype.guess(header_chunk)
    
    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only verified PDF, DOCX, and TXT files are allowed."
        )

    # 3. Check file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 10MB limit."
        )

    # 4. Generate secure randomized filename (prevent path traversal & collisions)
    file_extension = ALLOWED_MIME_TYPES[kind.mime]
    secure_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, secure_filename)

    # 5. Save safely to disk
    try:
        with open(file_path, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):  # Read in 1MB chunks
                buffer.write(chunk)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file."
        )

    return file_path
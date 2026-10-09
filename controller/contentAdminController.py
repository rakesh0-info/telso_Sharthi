import os
import shutil
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from database_config import get_db
from databaseModel.user_model import User
from databaseModel.Content_model import Content
from jwts.DB_Security_Config import require_roles
from enums.roleEnum import Role
from requestModel.Content_Request import CreateContentRequest

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router=APIRouter(prefix="/content_admin/api/v1")

@router.post("/add_content")
async def add_content(
    payload: str = Form(..., description="JSON string of CreateContentRequest"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.SUPER_ADMIN, Role.CONTENT_ADMIN))
):
    # 1. Parse the JSON string payload into the Pydantic model
    try:
        content_data = CreateContentRequest.model_validate_json(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON payload format: {str(e)}"
        )

    # 2. Save file locally
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_url = f"/{UPLOAD_DIR}/{file.filename}"

  
    new_content = Content(
        content_type=content_data.content_type,
        title=content_data.title,
        language_type=content_data.language_type,
        des=content_data.des,
        class_name=content_data.class_name,
        subject=content_data.subject,
        file_url=file_url,
        file_upload_state=content_data.file_upload_state,
        update_by=curr.id  
    )

    db.add(new_content)
    db.commit()
    db.refresh(new_content)

    return {
        "message": "Content added successfully",
        "content_id": new_content.id,
        "file_url": file_url,
        "uploaded_by": curr.email
    }   
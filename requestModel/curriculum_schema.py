from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enums.dbEnums import DocStatusEnum, DocTypeEnum, DbLanguageEnum


class DocumentCreate(BaseModel):
    document_name: str = Field(..., min_length=1, max_length=255)
    url: str
    class_id: int = Field(..., gt=0)
    subject_id: int = Field(..., gt=0)
    title: Optional[str] = Field(None, max_length=255)
    content_type: DocTypeEnum = DocTypeEnum.TEXT_BOOK
    language: DbLanguageEnum = DbLanguageEnum.ENGLISH
    status: DocStatusEnum = DocStatusEnum.READY


class DocumentResponse(BaseModel):
    id: int
    uploader_id: Optional[int] = None
    document_name: str
    url: str
    status: str
    class_id: int
    subject_id: int
    title: Optional[str] = None
    content_type: str
    language: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentEmbeddingCreate(BaseModel):
    document_id: int = Field(..., gt=0)
    chunk_index: int = Field(default=0, ge=0)
    content: str
    vector_embedding: str


class DocumentEmbeddingResponse(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    content: str
    vector_embedding: str

    class Config:
        from_attributes = True


class LessonGenerateRequest(BaseModel):
    teacher_id: int = Field(..., gt=0)
    school_id: int = Field(..., gt=0)
    class_id: int = Field(..., gt=0)
    section_id: int = Field(..., gt=0)
    subject_id: int = Field(..., gt=0)
    lesson_name: str = Field(..., min_length=1, max_length=255)
    generated_content_ai: str


class LessonGenerateResponse(BaseModel):
    id: int
    teacher_id: int
    school_id: int
    class_id: int
    section_id: int
    subject_id: int
    lession_name: str
    generated_content_ai: str
    created_at: datetime

    class Config:
        from_attributes = True


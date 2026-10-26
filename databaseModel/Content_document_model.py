from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from database_config import Base
from enums.contentEnum import UploadStateEnum

class ContentDocument(Base):
    __tablename__ = "content_documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=True, index=True)
    subject = Column(Integer, ForeignKey("subject.id"), nullable=True)  # Column remains 'subject'
    document_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    upload_status = Column(SQLEnum(UploadStateEnum, native_enum=False, create_type=False), default=UploadStateEnum.NOT_START, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    content = relationship("Content")
    chunks = relationship("ContentDocumentChunk", back_populates="document", cascade="all, delete-orphan")
    subject_obj = relationship("Subject", back_populates="documents")  # New relationship name

    
class ContentDocumentChunk(Base):
    __tablename__ = "content_document_chunks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("content_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    # Uncommented to store Gemini embeddings (3072 dimensions for gemini-embedding-001)
    embedding = Column(Vector(3072), nullable=True)

    document = relationship("ContentDocument", back_populates="chunks")
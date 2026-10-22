from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from database_config import Base
from enums.contentEnum import LanguageEnum
from enums.subjectEnum import subject
from enums.questionEnum import QuestionTypeEnum, DifficultyEnum, QuestionSetStatusEnum

class QuestionSet(Base):
    __tablename__ = "question_sets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    set_name = Column(String, nullable=False, index=True)
    class_name = Column(String, default="XII", nullable=False)
    subject = Column(SQLEnum(subject, native_enum=False, create_type=False), nullable=False)
    chapter = Column(String, nullable=False)
    topic = Column(String, nullable=True)
    language_type = Column(SQLEnum(LanguageEnum, native_enum=False, create_type=False), nullable=False)
    num_questions = Column(Integer, nullable=False)
    document_id = Column(Integer, ForeignKey("content_documents.id"), nullable=False)
    status = Column(SQLEnum(QuestionSetStatusEnum, native_enum=False, create_type=False), default=QuestionSetStatusEnum.DRAFT, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("ContentDocument")
    creator = relationship("User")
    questions = relationship("QuestionSetItem", back_populates="question_set", cascade="all, delete-orphan")


class QuestionSetItem(Base):
    __tablename__ = "question_set_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    question_set_id = Column(Integer, ForeignKey("question_sets.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(SQLEnum(QuestionTypeEnum, native_enum=False, create_type=False), nullable=False)
    difficulty_level = Column(SQLEnum(DifficultyEnum, native_enum=False, create_type=False), nullable=False)
    options = Column(JSON, nullable=True)           # Stores list of options for MCQs / Match Following
    correct_answer = Column(Text, nullable=False)   # Stores the exact correct answer(s)
    explanation = Column(Text, nullable=True)       # Detailed answer explanation
    source_reference = Column(String, nullable=True)# Chapter/page source reference

    question_set = relationship("QuestionSet", back_populates="questions")
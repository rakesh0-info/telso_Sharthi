from datetime import datetime, time
from typing import Optional, List
from pydantic import BaseModel, Field
from enums.dbEnums import DocStatusEnum


class QuizDocCreate(BaseModel):
    doc_name: str = Field(..., min_length=1, max_length=255)
    url: str
    status: DocStatusEnum = DocStatusEnum.READY


class QuizDocResponse(BaseModel):
    id: int
    uploader_id: Optional[int] = None
    doc_name: str
    url: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class QuizDocEmbeddingCreate(BaseModel):
    doc_id: int = Field(..., gt=0)
    chunk_index: int = Field(default=0, ge=0)
    content: str
    embedding: str


class QuizDocEmbeddingResponse(BaseModel):
    id: int
    doc_id: int
    chunk_index: int
    content: str
    embedding: str

    class Config:
        from_attributes = True


class QuizCreate(BaseModel):
    quiz_name: str = Field(..., min_length=1, max_length=255)
    total_question: int = Field(..., gt=0)
    school_id: int = Field(..., gt=0)
    class_id: int = Field(..., gt=0)
    section_id: int = Field(..., gt=0)
    teacher_id: int = Field(..., gt=0)
    quiz_time: int = Field(..., gt=0)  # in minutes
    publish: bool = False
    upload_quize_doc_id: Optional[int] = None


class QuizResponse(BaseModel):
    id: int
    quiz_name: str
    total_question: int
    school_id: int
    class_id: int
    section_id: int
    teacher_id: int
    no_of_register: int
    quiz_time: int
    publish: bool
    upload_quize_doc_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuizQuestionItem(BaseModel):
    question: str
    answer: str


class AddQuizQuestionsRequest(BaseModel):
    questions: List[QuizQuestionItem]


class QuizQuestionResponse(BaseModel):
    id: int
    quize_id: int
    quize_question: str
    quize_ans: str

    class Config:
        from_attributes = True


class QuizRegisterRequest(BaseModel):
    quiz_id: int = Field(..., gt=0)
    student_id: int = Field(..., gt=0)


class QuizRegistrationResponse(BaseModel):
    id: int
    quiz_id: int
    student_id: int
    class_id: int
    school_id: int
    section_id: int
    registered_at: datetime

    class Config:
        from_attributes = True


class StudentAnswerSubmission(BaseModel):
    question_id: Optional[int] = None
    selected_option: str


class QuizSubmitAssessmentRequest(BaseModel):
    quiz_id: int = Field(..., gt=0)
    student_id: int = Field(..., gt=0)
    time_taken_seconds: Optional[int] = None
    answers: List[StudentAnswerSubmission]


class QuizResultResponse(BaseModel):
    id: int
    quize_id: int
    student_id: int
    school_id: int
    class_id: int
    section_id: int
    total_score: int
    created_at: datetime

    class Config:
        from_attributes = True


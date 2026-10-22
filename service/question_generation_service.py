import os
import json
import logging
from sqlalchemy.orm import Session
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi import HTTPException,status

from databaseModel.Content_document_model import ContentDocument, ContentDocumentChunk
from databaseModel.QuestionSet_model import QuestionSet, QuestionSetItem
from requestModel.Question_Request import GenerateQuestionRequest
from enums.contentEnum import UploadStateEnum
from enums.questionEnum import QuestionSetStatusEnum


logger = logging.getLogger(__name__)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Pydantic schema for Gemini structured output guarantees correct answers & explanations format
class SingleGeneratedQuestion(BaseModel):
    question_text: str = Field(..., description="The text of the question.")
    question_type: str = Field(..., description="Type of question (e.g., MCQ, True / False, Short Answer, etc.)")
    difficulty_level: str = Field(..., description="Difficulty level (Easy, Medium, Hard)")
    options: Optional[List[str]] = Field(None, description="Options list if MCQ or Match the Following, otherwise null")
    correct_answer: str = Field(..., description="The correct answer or solution key.")
    explanation: Optional[str] = Field(None, description="Detailed explanation for the correct answer.")
    source_reference: Optional[str] = Field(None, description="Reference from the text (e.g. Chapter section/page).")

class AIQuestionResponseSchema(BaseModel):
    questions: List[SingleGeneratedQuestion]


def generate_question_set_with_ai(db: Session, payload: GenerateQuestionRequest, user_id: int) -> QuestionSet:
   
    doc = db.query(ContentDocument).filter(ContentDocument.id == payload.document_id).first()
    if not doc:
        raise ValueError("Selected reference document does not exist.")


    if doc.subject!=GenerateQuestionRequest.subject:
        raise HTTPException(status_code=400, detail=status.HTTP_400_BAD_REQUEST)
    
    
    if doc.upload_status != UploadStateEnum.READY:
        raise ValueError(f"Reference document is not ready yet. Current status: {doc.upload_status.value}")

  
    chunks = db.query(ContentDocumentChunk).filter(ContentDocumentChunk.document_id == doc.id).all()
    if not chunks:
        raise ValueError("No text chunks found for the selected document.")
    
    document_text = "\n\n".join([chunk.content for chunk in chunks])

   

    prompt = f"""
    You are an expert academic assessment creator. Generate exactly {payload.num_questions} questions with their correct answers, explanations, and source references based on the provided source text.
    and if possible write your own explanations  shot and simple explanations
    
    Configuration & Constraints:
    - Subject: {payload.subject.value}
    - Chapter: {payload.chapter}
    - Topic: {payload.topic or 'General'}
    - Language: {payload.language_type.value}
    - Allowed Question Types: {[qt.value for qt in payload.question_types]}
    - Allowed Difficulty Levels: {[dl.value for dl in payload.difficulty_levels]}
    - Include Answers & Explanations: {payload.include_explanations}
    - Include Source Reference: {payload.include_source_reference}

    Source Document Text:
    {document_text[:15000]}
    """ 


   
    try:
        
        response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AIQuestionResponseSchema,
            temperature=0.3,
        ),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=status.HTTP_503_SERVICE_UNAVAILABLE)
    

    ai_data = json.loads(response.text)

    
    question_set = QuestionSet(
        set_name=payload.set_name,
        class_name=payload.class_name,
        subject=payload.subject,
        chapter=payload.chapter,
        topic=payload.topic,
        language_type=payload.language_type,
        num_questions=payload.num_questions,
        document_id=payload.document_id,
        status=QuestionSetStatusEnum.DRAFT,
        created_by=user_id
    )
    db.add(question_set)
    db.flush()  # Flushes to generate question_set.id

    for q in ai_data.get("questions", []):
        question_item = QuestionSetItem(
            question_set_id=question_set.id,
            question_text=q.get("question_text"),
            question_type=q.get("question_type"),
            difficulty_level=q.get("difficulty_level"),
            options=q.get("options"),
            correct_answer=q.get("correct_answer"),       # Answer stored securely here
            explanation=q.get("explanation") if payload.include_explanations else None,
            source_reference=q.get("source_reference") if payload.include_source_reference else None
        )
        db.add(question_item)

    db.commit()
    db.refresh(question_set)
    return question_set
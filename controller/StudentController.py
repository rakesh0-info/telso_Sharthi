from datetime import datetime, timedelta, time
import os
import json
from typing import Annotated, List, Optional
from fastapi import APIRouter, HTTPException, Path, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from databaseModel.sync_model import LocalOfflineQuiz, LocalOfflineRegistration, LocalOfflineSubmission, SyncStatusEnum
from database_config import get_db
from databaseModel.School_model import School
from databaseModel.student_model import Student
from databaseModel.subject_model import Subject
from databaseModel.quiz_model import Quiz, QuizRegistration, QuizQuestionSet, QuizResult, QuizStudentAnswer
from enums.dbEnums import StatusEnum

router = APIRouter(prefix="/student/api/v1", tags=["Student Portal"])

JWT_SECRET_KEY = os.getenv("SECRET_KEY")
JWT_ALGORITHM = os.getenv("ALGORITHM")
TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
security = HTTPBearer()

class StudentLoginRequest(BaseModel):
    school_code: str = Field(..., min_length=1, max_length=50)
    roll_no: str = Field(..., min_length=1, max_length=50)

class OfflineAnswerSubmit(BaseModel):
    question_id: int
    selected_option: str = Field(..., min_length=1, max_length=255)

class OfflineQuizSubmissionRequest(BaseModel):
    quiz_id: int
    answers: List[OfflineAnswerSubmit]
    time_taken_seconds: Optional[int] = Field(None, ge=0, le=86400)

def get_current_student(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> Student:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        student_id: int = payload.get("sub")
        if student_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except (jwt.ExpiredSignatureError, jwt.PyJWTError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired or invalid")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or student.activation != StatusEnum.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student inactive or not found")
    return student

@router.get("/student/quizzes/{quiz_id}/load-offline", summary="Student loads offline quiz questions to attempt locally")
def load_offline_quiz_questions(
    quiz_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    offline_quiz = db.query(LocalOfflineQuiz).filter(
        LocalOfflineQuiz.quiz_id == quiz_id,
        LocalOfflineQuiz.school_id == current_student.school_id,
        LocalOfflineQuiz.class_id == current_student.class_id,
        LocalOfflineQuiz.section_id == current_student.section_id
    ).first()

    if not offline_quiz:
        raise HTTPException(status_code=404, detail="Quiz not found in local offline cache")

    if offline_quiz.is_start != 1:
        raise HTTPException(status_code=400, detail="Quiz has not started or has already ended in the lab.")

    try:
        questions_data = json.loads(offline_quiz.questions_json)
    except Exception:
        raise HTTPException(status_code=500, detail="Corrupted offline question payload")

    return {
        "success": True,
        "quiz_id": offline_quiz.quiz_id,
        "quiz_name": offline_quiz.quiz_name,
        "duration_minutes": offline_quiz.quiz_time_minutes,
        "total_questions": offline_quiz.total_questions,
        "questions": questions_data
    }

@router.post('/quizzes/{quiz_id}/offline-register', status_code=status.HTTP_201_CREATED, summary="Register to an offline quiz locally")
def register_to_offline_quiz(
    quiz_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    offline_quiz = db.query(LocalOfflineQuiz).filter(
        LocalOfflineQuiz.quiz_id == quiz_id,
        LocalOfflineQuiz.school_id == current_student.school_id,
        LocalOfflineQuiz.class_id == current_student.class_id,
        LocalOfflineQuiz.section_id == current_student.section_id
    ).first()

    if not offline_quiz:
        raise HTTPException(status_code=404, detail="Quiz not found in local offline storage")

    existing_reg = db.query(LocalOfflineRegistration).filter(
        LocalOfflineRegistration.quiz_id == quiz_id,
        LocalOfflineRegistration.student_id == current_student.id
    ).first()

    if existing_reg:
        raise HTTPException(status_code=409, detail="Already registered for this offline quiz")

    try:
        reg = LocalOfflineRegistration(
            quiz_id=quiz_id,
            student_id=current_student.id,
            school_id=current_student.school_id,
            class_id=current_student.class_id,
            section_id=current_student.section_id,
            sync_status=SyncStatusEnum.PENDING
        )
        db.add(reg)
        db.commit()
        return {"success": True, "message": "Successfully registered offline. Pending cloud sync."}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Registration conflict")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save offline registration") from exc

@router.post('/quizzes/offline-submit', status_code=status.HTTP_201_CREATED, summary="Submit answers offline and store in local lab sync queue")
def submit_offline_quiz_answer(
    payload: OfflineQuizSubmissionRequest,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student)
):
    offline_quiz = db.query(LocalOfflineQuiz).filter(
        LocalOfflineQuiz.quiz_id == payload.quiz_id,
        LocalOfflineQuiz.school_id == current_student.school_id,
        LocalOfflineQuiz.class_id == current_student.class_id,
        LocalOfflineQuiz.section_id == current_student.section_id
    ).first()

    if not offline_quiz:
        raise HTTPException(status_code=404, detail="Quiz not found in local offline cache")

    # Verify registration exists locally
    reg = db.query(LocalOfflineRegistration).filter(
        LocalOfflineRegistration.quiz_id == payload.quiz_id,
        LocalOfflineRegistration.student_id == current_student.id
    ).first()
    if not reg:
        raise HTTPException(status_code=403, detail="Must register for the offline quiz before submitting")

    existing_sub = db.query(LocalOfflineSubmission).filter(
        LocalOfflineSubmission.quiz_id == payload.quiz_id,
        LocalOfflineSubmission.student_id == current_student.id
    ).first()

    if existing_sub:
        raise HTTPException(status_code=409, detail="You have already submitted answers for this quiz offline")

    try:
        submission = LocalOfflineSubmission(
            quiz_id=payload.quiz_id,
            student_id=current_student.id,
            school_id=current_student.school_id,
            class_id=current_student.class_id,
            section_id=current_student.section_id,
            answers_json=json.dumps([a.model_dump() for a in payload.answers]),
            time_taken_seconds=payload.time_taken_seconds,
            sync_status=SyncStatusEnum.PENDING
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)

        return {
            "success": True,
            "message": "Answers stored safely in local offline table. Pending synchronization.",
            "submission_id": submission.id,
            "sync_status": submission.sync_status.value
        }
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate offline submission detected")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to store offline submission") from exc
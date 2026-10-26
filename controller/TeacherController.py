import io
import os
import shutil
import uuid
import json
from typing import Annotated, List, Optional
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import traceback

from database_config import SessionLocal, SessionLocal, get_db
from databaseModel.user_model import User
from databaseModel.teacher_model import Teacher
from databaseModel.student_model import Student
from databaseModel.class_model import ClassModel, ClassSection
from databaseModel.subject_model import Subject
from databaseModel.scheduler_model import ClassScheduler
from databaseModel.quiz_model import Quiz, QuizDoc, QuizQuestionSet, QuizRegistration
from databaseModel.lesson_model import LessonGenerate

from enums.roleEnum import Role
from enums.dbEnums import StatusEnum, DocStatusEnum
from jwts.DB_Security_Config import require_roles

from google import genai
from google.genai import types
from service.quiz_timer_service import handle_quiz_timer

router = APIRouter(prefix="/teacher/api/v1", tags=["Teacher Portal"])

# Initialize Gemini Client
ai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Ensure upload directory exists securely
UPLOAD_DIR = "uploads/quizzes"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==========================================
# HELPER: GET LOGGED-IN TEACHER PROFILE
# ==========================================
def get_teacher_profile(db: Session, curr: User) -> Teacher:
    teacher = db.query(Teacher).filter(Teacher.user_id == curr.id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found for this user")
    return teacher

# ==========================================
# HELPER: CLEAN AI JSON RESPONSE
# ==========================================
def parse_ai_json_response(text: str) -> list:
    """Safely extracts and parses JSON array from LLM output, removing markdown wrappers."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return json.loads(cleaned.strip())

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class QuizStartRequest(BaseModel):
    duration_minutes: int = Field(..., ge=1, le=180, description="Dynamic duration in minutes (1 to 180)")

class LessonGenerateRequest(BaseModel):
    class_id: int
    section_id: int
    topic_name: str = Field(..., min_length=2, max_length=255)
    language: str = Field(..., description="Select 'English' or 'Manipuri'")

class QuizCreateRequest(BaseModel):
    quiz_name: str = Field(..., min_length=2, max_length=255)
    class_id: int
    section_id: int
    subject_id: Optional[int] = None
    quiz_time_minutes: int = Field(30, ge=1, le=180)
    total_questions: int = Field(30, ge=5, le=50)

# ==========================================
# 1. GET ASSIGNED CLASSES, SUBJECTS & SCHEDULES
# ==========================================
@router.get('/assignments-and-schedule', summary="Get assigned classes, sections, subjects and schedules")
def get_teacher_assignments(db: Session = Depends(get_db),
                            curr: User = Depends(require_roles(Role.TEACHER, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    teacher = get_teacher_profile(db, curr)
    
    schedules = db.query(ClassScheduler).filter(ClassScheduler.teacher_id == curr.id).all()
    schedule_list = [{
        "schedule_id": sched.id,
        "class_name": sched.class_obj.class_name if sched.class_obj else None,
        "section_name": sched.section.section_name if sched.section else None,
        "subject_name": sched.subject.subject_name if sched.subject else None,
        "class_schedule": sched.class_schedule
    } for sched in schedules]

    primary_assignment = {
        "class_id": teacher.class_id,
        "class_name": teacher.class_obj.class_name if teacher.class_obj else None,
        "section_id": teacher.section,
        "section_name": teacher.section_obj.section_name if teacher.section_obj else None,
        "subject_id": teacher.subject,
        "subject_name": teacher.subject_obj.subject_name if teacher.subject_obj else None,
        "class_time": teacher.class_time
    }

    return {
        "success": True,
        "teacher_id": teacher.id,
        "school_id": teacher.school_id,
        "primary_assignment": primary_assignment,
        "scheduled_classes": schedule_list
    }

# ==========================================
# 2. STREAMED AI LESSON GENERATOR WITH STUDENTS
# ==========================================



@router.post('/lessons/generate-stream', summary="Stream AI lesson generator, show live & store in DB")
def generate_lesson_stream(payload: LessonGenerateRequest,
                           db: Session = Depends(get_db),
                           curr: User = Depends(require_roles(Role.TEACHER, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    teacher = get_teacher_profile(db, curr)

    # Secure Validation: Class & Section must belong to teacher's school
    class_obj = db.query(ClassModel).filter(
        ClassModel.id == payload.class_id,
        ClassModel.school_id == teacher.school_id
    ).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found or unauthorized")

    section_obj = db.query(ClassSection).filter(
        ClassSection.id == payload.section_id,
        ClassSection.class_id == payload.class_id
    ).first()
    if not section_obj:
        raise HTTPException(status_code=404, detail="Section not found in this class")

    students = db.query(Student).filter(
        Student.school_id == teacher.school_id,
        Student.class_id == payload.class_id,
        Student.section_id == payload.section_id
    ).all()
    student_count = len(students)

    lang = payload.language.strip().capitalize()
    if lang not in ["English", "Manipuri"]:
        raise HTTPException(status_code=422, detail="Language must be either 'English' or 'Manipuri'")

    prompt = (
        f"Generate a comprehensive lesson plan for the topic '{payload.topic_name}' "
        f"for Class {class_obj.class_name} Section {section_obj.section_name}. "
        f"The output language must be strictly in {lang}. "
        f"Include learning objectives, introduction, core concepts, interactive activities, and assessment questions."
    )

    def streaming_and_saving_generator():
        accumulated_chunks = []
        try:
            print(f"[AI Stream] Starting generation for topic: {payload.topic_name} in {lang}...")
            # Use gemini-2.0-flash as a stable standard model
            response = ai_client.models.generate_content_stream(
                model='gemini-3.8-flash',
                contents=prompt
            )
            for chunk in response:
                chunk_text = getattr(chunk, 'text', None)
                if chunk_text:
                    accumulated_chunks.append(chunk_text)
                    yield chunk_text  # Streams live to client
        except Exception as e:
            print("[AI Stream Error] Exception encountered during streaming:")
            traceback.print_exc()
            error_msg = f"\n[Error generating AI lesson stream: {str(e)}]"
            accumulated_chunks.append(error_msg)
            yield error_msg
        finally:
            full_content = "".join(accumulated_chunks)
            print(f"[AI Stream] Finished. Total content length stored: {len(full_content)} chars.")
            
            # Save complete response to DB using a fresh session
            background_db = SessionLocal()
            try:
                lesson_record = LessonGenerate(
                    teacher_id=teacher.id,
                    school_id=teacher.school_id,
                    class_id=payload.class_id,
                    section_id=payload.section_id,
                    subject_id=teacher.subject or 1,
                    lession_name=payload.topic_name,
                    generated_content_ai=full_content
                )
                background_db.add(lesson_record)
                background_db.commit()
                print("[AI Stream] Lesson record successfully committed to database.")
            except SQLAlchemyError as db_err:
                background_db.rollback()
                print(f"[Database Error] Failed to save streamed lesson: {str(db_err)}")
            finally:
                background_db.close()

    return StreamingResponse(streaming_and_saving_generator(), media_type="text/plain")


# ==========================================
# 3. CREATE QUIZ (SECURE UPLOAD & 30 MCQ GENERATION)
# ==========================================
@router.post('/quizzes/create', status_code=status.HTTP_201_CREATED, summary="Create quiz, process document & generate MCQs")
def create_quiz(
    quiz_name: str = Form(..., min_length=2, max_length=255),
    class_id: int = Form(...),
    section_id: int = Form(...),
    subject_id: Optional[int] = Form(None),
    quiz_time_minutes: int = Form(30),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.TEACHER, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))
):
    teacher = get_teacher_profile(db, curr)

    # Secure Validation: Class & Section authorization check
    class_obj = db.query(ClassModel).filter(
        ClassModel.id == class_id,
        ClassModel.school_id == teacher.school_id
    ).first()
    if not class_obj:
        raise HTTPException(status_code=403, detail="Unauthorized class selection for your school")

    section_obj = db.query(ClassSection).filter(
        ClassSection.id == section_id,
        ClassSection.class_id == class_id
    ).first()
    if not section_obj:
        raise HTTPException(status_code=404, detail="Section does not belong to the specified class")

    # Validate file extension and size
    if not file.filename or not file.filename.lower().endswith(('.pdf', '.txt', '.docx')):
        raise HTTPException(status_code=400, detail="Supported formats: PDF, TXT, DOCX")

    file_bytes = file.file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds 10MB limit")

    # Secure File Storage with UUID to prevent path traversal
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)

        # 1. Store Quiz Document record
        quiz_doc = QuizDoc(
            uploader_id=curr.id,
            school_id=teacher.school_id,
            class_id=class_id,
            doc_name=file.filename,
            url=file_path,
            status=DocStatusEnum.READY
        )
        db.add(quiz_doc)
        db.flush()

        # 2. Create Quiz entry
        quiz = Quiz(
            quiz_name=quiz_name,
            total_question=30,
            school_id=teacher.school_id,
            class_id=class_id,
            section_id=section_id,
            teacher_id=teacher.id,
            quiz_time=quiz_time_minutes,
            publish=False,
            is_start=False,
            upload_quize_doc_id=quiz_doc.id
        )
        db.add(quiz)
        db.flush()

        # 3. Generate 30 MCQs using Gemini safely
        prompt = (
            f"Generate exactly 30 Multiple Choice Questions (MCQs) based on the subject matter of '{quiz_name}'. "
            "Return the output strictly as a JSON array of objects with keys: 'question', 'options' (list of 4 options), and 'answer'."
        )
        
        ai_resp = ai_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )

        questions_data = []
        if ai_resp.text:
            questions_data = parse_ai_json_response(ai_resp.text)

        # 4. Insert Question Set items
        for q in questions_data[:30]:
            q_set_item = QuizQuestionSet(
                quiz_id=quiz.id,
                quize_question=q.get("question"),
                quize_ans=q.get("answer")
            )
            db.add(q_set_item)

        db.commit()
        db.refresh(quiz)

        return {
            "success": True,
            "message": "Quiz created and 30 MCQs successfully generated via AI",
            "quiz_id": quiz.id,
            "total_questions": len(questions_data)
        }

    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create quiz: {str(exc)}") from exc

# ==========================================
# 4. PUBLISH QUIZ
# ==========================================
@router.patch('/quizzes/{quiz_id}/publish', summary="Publish a quiz")
def publish_quiz(quiz_id: Annotated[int, Path(gt=0)],
                 db: Session = Depends(get_db),
                 curr: User = Depends(require_roles(Role.TEACHER, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    teacher = get_teacher_profile(db, curr)
    
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.teacher_id == teacher.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or unauthorized")

    quiz.publish = True
    db.commit()
    return {"success": True, "message": f"Quiz '{quiz.quiz_name}' published successfully"}

# ==========================================
# 5. START QUIZ (WITH ROW LOCKING & TIMER)
# ==========================================
@router.post('/quizzes/{quiz_id}/start', summary="Start quiz with dynamic timer and background auto-stop")
def start_quiz(
    quiz_id: Annotated[int, Path(gt=0)],
    payload: QuizStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.TEACHER, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))
):
    teacher = get_teacher_profile(db, curr)
    
    # Use with_for_update() to prevent race conditions on concurrent starts
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.teacher_id == teacher.id).with_for_update().first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or unauthorized")
    
    if not quiz.publish:
        raise HTTPException(status_code=400, detail="Cannot start an unpublished quiz. Publish it first.")

    if quiz.is_start:
        raise HTTPException(status_code=400, detail="Quiz is already running.")

    quiz.is_start = True
    quiz.quiz_time = payload.duration_minutes
    db.commit()

    # Trigger background timer task
    background_tasks.add_task(handle_quiz_timer, quiz_id=quiz.id, duration_minutes=payload.duration_minutes)

    return {
        "success": True,
        "message": f"Quiz started successfully with a timer of {payload.duration_minutes} minutes.",
        "quiz_id": quiz.id,
        "quiz_name": quiz.quiz_name,
        "is_start": True,
        "duration_minutes": payload.duration_minutes,
        "started_at": datetime.utcnow()
    }

# ==========================================
# 6. SEE WHO REGISTERED FOR THE QUIZ
# ==========================================
@router.get('/quizzes/{quiz_id}/registrations', summary="View students registered for the quiz")
def get_quiz_registrations(quiz_id: Annotated[int, Path(gt=0)],
                           db: Session = Depends(get_db),
                           curr: User = Depends(require_roles(Role.TEACHER, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    teacher = get_teacher_profile(db, curr)
    
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.teacher_id == teacher.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or unauthorized")

    registrations = db.query(QuizRegistration).filter(QuizRegistration.quiz_id == quiz_id).all()
    student_records = []
    for reg in registrations:
        student = reg.student
        if student:
            student_records.append({
                "student_id": student.id,
                "roll_no": student.role_no,
                "name": student.name,
                "registered_at": reg.registered_at
            })

    return {
        "success": True,
        "quiz_id": quiz.id,
        "quiz_name": quiz.quiz_name,
        "total_registrations": len(student_records),
        "registered_students": student_records
    }

# ==========================================
# 7. GET ALL QUIZZES CREATED BY TEACHER
# ==========================================
@router.get('/quizzes/all', summary="Get all quizzes created by teacher")
def get_all_teacher_quizzes(db: Session = Depends(get_db),
                            curr: User = Depends(require_roles(Role.TEACHER, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    teacher = get_teacher_profile(db, curr)
    quizzes = db.query(Quiz).filter(Quiz.teacher_id == teacher.id).all()
    
    result = [{
        "quiz_id": q.id,
        "quiz_name": q.quiz_name,
        "total_questions": q.total_question,
        "quiz_time_minutes": q.quiz_time,
        "is_published": q.publish,
        "is_start": q.is_start,
        "registrations_count": q.no_of_register,
        "created_at": q.created_at
    } for q in quizzes]

    return {"success": True, "count": len(result), "quizzes": result}
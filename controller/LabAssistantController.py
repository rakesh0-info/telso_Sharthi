import asyncio
from datetime import datetime, timezone
import json
import os
from typing import Annotated, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import requests

from databaseModel.quiz_model import Quiz, QuizQuestionSet
from databaseModel.sync_model import LocalOfflineQuiz, LocalOfflineRegistration, LocalOfflineSubmission, SyncStatusEnum
from database_config import SessionLocal, get_db
from databaseModel.user_model import User
from databaseModel.School_model import School
from databaseModel.lab_model import Lab
from databaseModel.Content_model import Content
from databaseModel.Content_document_model import ContentDocument

from enums.roleEnum import Role
from enums.dbEnums import StatusEnum
from jwts.DB_Security_Config import require_roles

router = APIRouter(prefix="/lab_assistant/api/v1", tags=["Lab Assistant Portal"])

CENTRAL_CLOUD_URL = os.getenv("CENTRAL_CLOUD_URL", "http://127.0.0.1:8000")
BASE_UPLOAD_DIR = os.path.abspath("uploads")

def get_lab_assistant_profile(db: Session, curr: User) -> Lab:
    lab = db.query(Lab).filter(Lab.lab_assistant_id == curr.id).first()
    if not lab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lab profile not found for this user account")
    if lab.activation != StatusEnum.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Lab account is currently inactive")
    return lab

@router.get("/dashboard", summary="Lab Assistant Dashboard")
def lab_assistant_dashboard(
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.LAB_ASSISTANT, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))
):
    lab = get_lab_assistant_profile(db, curr)
    school = db.query(School).filter(School.id == lab.school_id).first()
    return {
        "success": True,
        "message": "Welcome to the Lab Assistant Portal",
        "assistant_info": {"user_id": curr.id, "name": curr.name, "email": curr.email, "phone": curr.phonenumber},
        "lab_details": {"lab_id": lab.id, "lab_name": lab.lab_name, "activation_status": lab.activation.value},
        "school_details": {"school_id": school.id if school else None, "school_name": school.school_name if school else None}
    }

@router.get("/quizzes/download-all", summary="Fetch published central quizzes and cache questions locally securely")
def download_quizzes_for_offline(
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.LAB_ASSISTANT, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))
):
    lab = get_lab_assistant_profile(db, curr)
    quizzes = db.query(Quiz).filter(Quiz.school_id == lab.school_id, Quiz.publish == True).all()

    if not quizzes:
        return {"success": True, "message": "No published quizzes found", "downloaded_count": 0}

    downloaded = 0
    for q in quizzes:
        q_items = db.query(QuizQuestionSet).filter(QuizQuestionSet.quiz_id == q.id).all()
        questions_list = [{
            "question_id": item.id,
            "question": item.quize_question,
            "options": getattr(item, "options", [])
        } for item in q_items]

        existing = db.query(LocalOfflineQuiz).filter(LocalOfflineQuiz.quiz_id == q.id).first()
        if not existing:
            local_q = LocalOfflineQuiz(
                quiz_id=q.id,
                teacher_id=q.teacher_id,
                subject_id=q.subject_id,
                school_id=q.school_id,
                class_id=q.class_id,
                section_id=q.section_id,
                quiz_name=q.quiz_name,
                total_questions=q.total_question,
                quiz_time_minutes=q.quiz_time,
                questions_json=json.dumps(questions_list),
                is_start=0
            )
            db.add(local_q)
            downloaded += 1
        else:
            existing.questions_json = json.dumps(questions_list)

    db.commit()
    return {"success": True, "message": f"Successfully downloaded {downloaded} quizzes securely (answers stripped)", "downloaded_count": downloaded}

async def handle_offline_quiz_timer(quiz_id: int, duration_minutes: int):
    await asyncio.sleep(duration_minutes * 60)
    db: Session = SessionLocal()
    try:
        local_q = db.query(LocalOfflineQuiz).filter(LocalOfflineQuiz.quiz_id == quiz_id).first()
        if local_q and local_q.is_start == 1:
            local_q.is_start = 2  # 2 = Ended / Auto-submitted
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

@router.post("/quizzes/{quiz_id}/start-offline", summary="Start quiz locally in lab with timer")
def start_offline_quiz(
    quiz_id: Annotated[int, Path(gt=0)],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.LAB_ASSISTANT, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))
):
    get_lab_assistant_profile(db, curr)
    local_q = db.query(LocalOfflineQuiz).filter(LocalOfflineQuiz.quiz_id == quiz_id).first()
    if not local_q:
        raise HTTPException(status_code=404, detail="Quiz not found in local offline storage")

    if local_q.is_start == 1:
        raise HTTPException(status_code=400, detail="Offline quiz is already running")

    local_q.is_start = 1
    db.commit()

    background_tasks.add_task(handle_offline_quiz_timer, quiz_id=quiz_id, duration_minutes=local_q.quiz_time_minutes)

    return {
        "success": True,
        "message": f"Offline quiz '{local_q.quiz_name}' started with a timer of {local_q.quiz_time_minutes} minutes.",
        "quiz_id": local_q.quiz_id,
        "is_start": 1
    }

def execute_sync_background(reg_ids: List[int], sub_ids: List[int]):
    db = SessionLocal()
    try:
        # Sync Registrations
        pending_regs = db.query(LocalOfflineRegistration).filter(
            LocalOfflineRegistration.id.in_(reg_ids),
            LocalOfflineRegistration.sync_status.in_([SyncStatusEnum.PENDING, SyncStatusEnum.FAILED])
        ).all()
        for r in pending_regs:
            r.sync_status = SyncStatusEnum.SYNCING
        db.commit()

        for r in pending_regs:
            try:
                payload = {"quiz_id": r.quiz_id, "student_id": r.student_id, "school_id": r.school_id, "class_id": r.class_id, "section_id": r.section_id}
                res = requests.post(f"{CENTRAL_CLOUD_URL}/teacher/api/v1/sync/receive-registration", json=payload, timeout=10)
                if res.status_code == 200:
                    r.sync_status = SyncStatusEnum.SYNCED
                    r.synced_at = datetime.now(timezone.utc)
                else:
                    r.sync_status = SyncStatusEnum.FAILED
                    r.sync_error = res.text[:200]
            except Exception as e:
                r.sync_status = SyncStatusEnum.FAILED
                r.sync_error = str(e)
        db.commit()

        # Sync Submissions
        pending_subs = db.query(LocalOfflineSubmission).filter(
            LocalOfflineSubmission.id.in_(sub_ids),
            LocalOfflineSubmission.sync_status.in_([SyncStatusEnum.PENDING, SyncStatusEnum.FAILED])
        ).all()
        for s in pending_subs:
            s.sync_status = SyncStatusEnum.SYNCING
        db.commit()

        for s in pending_subs:
            try:
                payload = {
                    "quiz_id": s.quiz_id,
                    "student_id": s.student_id,
                    "answers": json.loads(s.answers_json),
                    "time_taken_seconds": s.time_taken_seconds
                }
                res = requests.post(f"{CENTRAL_CLOUD_URL}/teacher/api/v1/sync/receive-submission", json=payload, timeout=15)
                if res.status_code == 200:
                    s.sync_status = SyncStatusEnum.SYNCED
                    s.synced_at = datetime.now(timezone.utc)
                else:
                    s.sync_status = SyncStatusEnum.FAILED
                    s.sync_error = res.text[:200]
            except Exception as e:
                s.sync_status = SyncStatusEnum.FAILED
                s.sync_error = str(e)
        db.commit()
    finally:
        db.close()

@router.post("/sync/trigger-and-submit", summary="Trigger sync for local registrations and submissions to teacher portal")
def trigger_sync_and_submit(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    curr: User = Depends(require_roles(Role.LAB_ASSISTANT, Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))
):
    get_lab_assistant_profile(db, curr)
    pending_regs = db.query(LocalOfflineRegistration).filter(LocalOfflineRegistration.sync_status.in_([SyncStatusEnum.PENDING, SyncStatusEnum.FAILED])).all()
    pending_subs = db.query(LocalOfflineSubmission).filter(LocalOfflineSubmission.sync_status.in_([SyncStatusEnum.PENDING, SyncStatusEnum.FAILED])).all()

    if not pending_regs and not pending_subs:
        return {"success": True, "message": "All offline records are already synchronized."}

    reg_ids = [r.id for r in pending_regs]
    sub_ids = [s.id for s in pending_subs]

    background_tasks.add_task(execute_sync_background, reg_ids, sub_ids)
    return {"success": True, "message": f"Sync triggered successfully for {len(reg_ids)} registrations and {len(sub_ids)} submissions.", "status": "PROCESSING"}
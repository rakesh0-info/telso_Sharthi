import io
import os
import shutil
from typing import Annotated, List
import uuid
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status, Depends, UploadFile, File, Form

from fastapi.responses import StreamingResponse
import pandas as pd
from pydantic import ValidationError
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from collections import Counter
import math

from databaseModel.School_model import School
from enums.userActivationEnum import activation
from mail.sendmail import send_teacher_welcome_email
from otp_generate.randomKey import get_random_letters, get_random_pass
from requestModel.Action import contentAdminAction
from requestModel.Question_Request import GenerateQuestionRequest
from requestModel.teacherSchema import ClassSectionAssignment, TeacherCreate, TeacherResponse, validate_assignment_list
from service.question_generation_service import generate_question_set_with_ai
from database_config import get_db
from databaseModel.user_model import User
from databaseModel.Content_model import Content
from databaseModel.Content_document_model import ContentDocument
from jwts.DB_Security_Config import require_roles
from enums.roleEnum import Role
from requestModel.Content_Request import CreateContentRequest
from databaseModel.QuestionSet_model import QuestionSetItem as questions, QuestionSet as q_set

from enums.contentEnum import UploadStateEnum
from service.content_rag_service import process_content_document_background
from enums.questionEnum import QuestionSetStatusEnum, QuestionTypeEnum as question_types
from enums.questionEnum import QuestionSetStatusEnum as question_status

from databaseModel.QuestionSet_model import QuestionSet, QuestionSetItem
from requestModel.Submission_Request import SubmitAssessmentRequest
from google import genai
from google.genai import types
import json

from util_validate.password_security import hash_password
from databaseModel.user_model import teacher_classes


router = APIRouter(prefix="/school_admin/api/v1")


@router.get("/dashboard")
async def dashboard(curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    return "this is School admin Dashboard"


def authorize_school(db: Session, curr: User, school_id: int) -> School:
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise HTTPException(404, 'School not found')
    if curr.role == Role.SCHOOL_ADMIN:
        # School.admin_id is the actual admin ownership relation in your project.
        if school.admin_id != curr.id:
            raise HTTPException(403, 'You are not the administrator of this school')
    return school


def assignment_rows(teacher_id: int, assignments: List[ClassSectionAssignment]):
    validate_assignment_list(assignments)
    return [dict(user_id=teacher_id, class_name=a.class_name.value,
                 section_name=a.section_name.value if a.section_name else None)
            for a in assignments]


def get_assignments(db: Session, teacher_id: int):
    rows = db.execute(select(teacher_classes.c.class_name, teacher_classes.c.section_name)
                      .where(teacher_classes.c.user_id == teacher_id)
                      .order_by(teacher_classes.c.class_name, teacher_classes.c.section_name)).all()
    return [ClassSectionAssignment(class_name=r.class_name, section_name=r.section_name) for r in rows]


def teacher_response(db: Session, teacher: User):
    data = TeacherResponse.model_validate(teacher)
    data.subjects = teacher.subject
    data.assignments = get_assignments(db, teacher.id)
    return data


def create_teacher_transaction(db: Session, school_id: int, first_name: str, last_name: str,
                               email: str, phone: str | None, subject: str | None,
                               assignments: List[ClassSectionAssignment], active=activation.ACTIVE):
    # The caller owns commit/rollback. Flush obtains the ID without committing.
    password = get_random_pass()
    teacher = User(school_id=school_id, first_Name=first_name, last_Name=last_name,
                   email=email.strip().lower(), phone=phone, subject=subject,
                   password=hash_password(password), role=Role.TEACHER,
                   activation_status=active, last_login=None)
    db.add(teacher)
    db.flush()
    rows = assignment_rows(teacher.id, assignments)
    if rows:
        db.execute(insert(teacher_classes), rows)
    db.flush()
    return teacher, password


def send_welcome_safely(teacher: User, password: str, school: School):
    try:
        send_teacher_welcome_email(to_email=teacher.email,
                                   teacher_name=f'{teacher.first_Name} {teacher.last_Name}',
                                   temp_password=password, school_obj=school)
    except Exception:
        # logger.exception('Teacher created, but welcome email failed for teacher ID %s', teacher.id)
        print("execption")
        # For reliable delivery, use a transactional outbox and a retrying worker.


@router.post('/addTeacher', response_model=TeacherResponse, status_code=201)
def add_teacher(payload: TeacherCreate, db: Session = Depends(get_db),
                curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    try:
        school = authorize_school(db, curr, payload.school_id)
        teacher, password = create_teacher_transaction(
            db, payload.school_id, payload.first_Name, payload.last_Name,
            str(payload.email), payload.phone, payload.subjects, payload.assignments)
        db.commit()
        db.refresh(teacher)
        response = teacher_response(db, teacher)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Teacher email or assignment conflicts with existing data')
    except SQLAlchemyError:
        db.rollback()
        # logger.exception('Teacher creation database failure')
        raise HTTPException(500, 'Could not create teacher')
    send_welcome_safely(teacher, password, school)
    return response


@router.get('/getallTeacher', response_model=List[TeacherResponse])
def get_all_teachers(school_id: int, db: Session = Depends(get_db),
                     curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, school_id)
    teachers = db.query(User).filter(User.role == Role.TEACHER, User.school_id == school_id).all()
    return [teacher_response(db, teacher) for teacher in teachers]


@router.post('/{teacher_id}/assign-classes', status_code=200)
def assign_classes_to_teacher(teacher_id: Annotated[int, Path(gt=0)],
                              assignments: List[ClassSectionAssignment],
                              db: Session = Depends(get_db),
                              curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    if not assignments:
        raise HTTPException(422, 'At least one assignment is required; use a separate clear endpoint to remove all')
    if len(assignments) > 100:
        raise HTTPException(422, 'Too many assignments (maximum 100)')
    try:
        rows = assignment_rows(teacher_id, assignments)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        teacher = db.query(User).filter(User.id == teacher_id, User.role == Role.TEACHER).with_for_update().first()
        if teacher is None:
            raise HTTPException(404, 'Teacher not found')
        if teacher.school_id is None:
            raise HTTPException(422, 'Teacher is not assigned to a school')
        authorize_school(db, curr, teacher.school_id)
        if teacher.activation_status != activation.ACTIVE:
            raise HTTPException(403, 'Inactive teacher cannot receive assignments')
        db.execute(delete(teacher_classes).where(teacher_classes.c.user_id == teacher_id))
        db.execute(insert(teacher_classes), rows)
        db.commit()
        return {'success': True, 'teacher_id': teacher_id, 'school_id': teacher.school_id,
                'total_assignments': len(rows), 'assignments': [
                    {'class_name': r['class_name'], 'section_name': r['section_name']} for r in rows]}
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Assignment conflicts with database constraints')
    except SQLAlchemyError:
        db.rollback()
      
        raise HTTPException(500, 'Could not update teacher assignments')


def parse_excel_classes(value) -> List[ClassSectionAssignment]:
    if pd.isna(value) or not str(value).strip():
        return []
    parsed = []
    for raw in str(value).split(','):
        entry = raw.strip().upper()
        if not entry:
            raise ValueError('Empty class entry in Classes cell')
        if entry in {'11', '12'}:
            data = {'class_name': entry, 'section_name': None}
        elif entry in {'8A','8B','9A','9B','10A','10B'}:
            cls = entry[:-1]
            data = {'class_name': cls, 'section_name': entry}
        else:
            raise ValueError(f'Invalid class/section entry: {entry}')
        parsed.append(ClassSectionAssignment.model_validate(data))
    return validate_assignment_list(parsed)




@router.get("/download-template", response_model=None,summary="Download Teacher Bulk Upload Excel Template")
async def download_teacher_template(curr:User=Depends(require_roles(Role.SCHOOL_ADMIN,Role.SUPER_ADMIN))):
    data = {
        "Full Name": ["Anita Devi", "Raj Kumar"],
        "Email": ["anita.devi@sunrise.edu.in", "raj.kumar@sunrise.edu.in"],
        "Phone": ["9876543210", "9876543211"],
        "Subject": ["Science", "Mathematics"],
        "Classes": ["8A,8B", "9A,9B"],
        "Status": ["Active", "Active"]
    }
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Teachers")
    output.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="teacher_bulk_upload_template.xlsx"'
    }
    return StreamingResponse(
        output,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



    
@router.post('/bulk-upload')
def bulk_upload_teachers(school_id: int = Form(...), file: UploadFile = File(...),
                         db: Session = Depends(get_db),
                         curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    if school_id <= 0:
        raise HTTPException(422, 'Invalid school ID')
    school = authorize_school(db, curr, school_id)
    if not file.filename or not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(400, 'Only .xlsx files are supported')
    # Limit decompression and parser exposure; tune to your deployment capacity.
    content = file.file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, 'Excel file exceeds 5 MB')
    try:
        df = pd.read_excel(io.BytesIO(content), engine='openpyxl', dtype=str)
    except Exception:
        raise HTTPException(400, 'Invalid Excel file')
    required = {'Full Name','Email','Phone','Subject','Classes','Status'}
    if not required.issubset(df.columns):
        raise HTTPException(422, f'Missing columns: {sorted(required - set(df.columns))}')
    if len(df) > 1000:
        raise HTTPException(413, 'Maximum 1000 rows per upload')
    from pydantic import EmailStr, TypeAdapter
    email_adapter = TypeAdapter(EmailStr)
    successes, failures, seen_emails = 0, [], set()
    for index, row in df.iterrows():
        row_number = index + 2
        email = ''
        try:
            name = str(row['Full Name']).strip() if pd.notna(row['Full Name']) else ''
            parts = name.split(maxsplit=1)
            if not parts:
                raise ValueError('Full Name is required')
            email = str(email_adapter.validate_python(str(row['Email']).strip().lower()))
            if email in seen_emails:
                raise ValueError('Duplicate email in upload')
            seen_emails.add(email)
            state = str(row['Status']).strip().lower() if pd.notna(row['Status']) else 'active'
            if state not in {'active', 'inactive'}:
                raise ValueError('Status must be Active or Inactive')
            assignments = parse_excel_classes(row['Classes'])
            phone = str(row['Phone']).strip() if pd.notna(row['Phone']) else None
            subject = str(row['Subject']).strip() if pd.notna(row['Subject']) else None
            teacher, password = create_teacher_transaction(
                db, school_id, parts[0], parts[1] if len(parts) > 1 else '',
                email, phone, subject, assignments,
                activation.ACTIVE if state == 'active' else activation.INACTIVE)
            db.commit()
            successes += 1
            send_welcome_safely(teacher, password, school)
        except (ValueError, ValidationError, IntegrityError, SQLAlchemyError) as exc:
            db.rollback()
            failures.append({'row': row_number, 'email': email, 'error':
                             'Database conflict' if isinstance(exc, IntegrityError) else str(exc)})
    return {'total_rows_processed': len(df), 'success_count': successes,
            'failure_count': len(failures), 'failed_rows': failures}

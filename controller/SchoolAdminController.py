import io
import os
from typing import Annotated, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Path, status, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import pandas as pd
from pydantic import BaseModel, EmailStr, TypeAdapter, TypeAdapter, ValidationError
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database_config import get_db
from databaseModel.School_model import School
from databaseModel.user_model import User
from databaseModel.teacher_model import Teacher
from databaseModel.student_model import Student
from databaseModel.class_model import ClassModel, ClassSection
from databaseModel.subject_model import Subject
from databaseModel.lab_model import Lab
from databaseModel.scheduler_model import ClassScheduler

from enums.roleEnum import Role
from enums.dbEnums import StatusEnum
from jwts.DB_Security_Config import require_roles
from mail.sendmail import send_teacher_welcome_email
from otp_generate.randomKey import get_random_pass
from util_validate.password_security import hash_password

router = APIRouter(prefix="/school_admin/api/v1", tags=["School Admin"])

# ==========================================
# PYDANTIC REQUEST SCHEMAS
# ==========================================

class TeacherCreateRequest(BaseModel):
    school_id: int
    first_Name: str
    last_Name: str
    email: EmailStr
    phone: Optional[str] = None
    subject_id: Optional[int] = None
    class_id: Optional[int] = None
    section_id: Optional[int] = None
    class_time: Optional[str] = None

class TeacherAssignRequest(BaseModel):
    class_id: int
    section_id: Optional[int] = None
    subject_id: Optional[int] = None
    class_time: Optional[str] = None

class LabAssistantCreateRequest(BaseModel):
    school_id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    lab_name: str

class StudentCreateRequest(BaseModel):
    school_id: int
    class_id: int
    section_id: int
    roll_no: str
    name: str
    parents_name: Optional[str] = None
    parents_phone: Optional[str] = None

class ClassCreateRequest(BaseModel):
    school_id: int
    class_name: str
    grade_level: Optional[str] = None

class SectionCreateRequest(BaseModel):
  
    class_id: int
    section_name: str

class SubjectCreateRequest(BaseModel):
    school_id: int
    class_id: int
    subject_name: str

class ClassScheduleRequest(BaseModel):
    school_id: int
    class_id: int
    section_id: int
    subject_id: int
    teacher_id: int  # References User.id
    class_schedule: datetime

# ==========================================
# HELPER AUTHORIZATION
# ==========================================

def authorize_school(db: Session, curr: User, school_id: int) -> School:
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    if curr.role == Role.SCHOOL_ADMIN:
        if school.school_admin_id != curr.id:
            raise HTTPException(status_code=403, detail="You are not the administrator of this school")
    return school

# ==========================================
# DASHBOARD
# ==========================================

@router.get("/dashboard")
async def dashboard(curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    return {"message": "Welcome to the School Admin Dashboard", "admin": curr.name}

# ==========================================
# 1. ADD TEACHER & ASSIGNMENTS
# ==========================================

@router.post('/addTeacher', status_code=status.HTTP_201_CREATED)
def add_teacher(payload: TeacherCreateRequest, db: Session = Depends(get_db),
                curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    school = authorize_school(db, curr, payload.school_id)
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    temp_password = get_random_pass()
    try:
        # Create User entry for authentication
        user = User(
            school_id=payload.school_id,
            name=f"{payload.first_Name} {payload.last_Name}",
            email=payload.email.strip().lower(),
            password=hash_password(temp_password),
            role=Role.TEACHER,
            phonenumber=payload.phone,
            activation=StatusEnum.ACTIVE
        )
        db.add(user)
        db.flush()  # Get user.id

        # Create Teacher profile entity linked to User and School
        teacher = Teacher(
            user_id=user.id,
            school_id=payload.school_id,
            class_id=payload.class_id,
            section=payload.section_id,
            subject=payload.subject_id,
            class_time=payload.class_time
        )
        db.add(teacher)
        db.commit()
        db.refresh(user)
        db.refresh(teacher)

        # Send welcome email asynchronously / safely
        try:
            send_teacher_welcome_email(
                to_email=user.email,
                teacher_name=user.name,
                temp_password=temp_password,
                school_obj=school
            )
        except Exception:
            pass  # Log email failure if needed without breaking transaction

        return {
            "success": True,
            "message": "Teacher added successfully",
            "teacher_id": teacher.id,
            "user_id": user.id,
            "temporary_password": temp_password
        }
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Database integrity error during teacher creation") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create teacher due to a database error") from exc

@router.post('/teachers/{teacher_id}/assign', status_code=status.HTTP_200_OK)
def assign_teacher_classes(teacher_id: Annotated[int, Path(gt=0)],
                           payload: TeacherAssignRequest,
                           db: Session = Depends(get_db),
                           curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    
    authorize_school(db, curr, teacher.school_id)

    try:
        teacher.class_id = payload.class_id
        teacher.section = payload.section_id
        teacher.subject = payload.subject_id
        if payload.class_time:
            teacher.class_time = payload.class_time
        
        db.commit()
        return {"success": True, "message": "Teacher class/subject assignment updated successfully"}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update teacher assignments") from exc

@router.delete('/teachers/{teacher_id}/separate', status_code=status.HTTP_200_OK)
def separate_teacher(teacher_id: Annotated[int, Path(gt=0)],
                     db: Session = Depends(get_db),
                     curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    """Separates/removes teacher association or deactivates teacher profile."""
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    authorize_school(db, curr, teacher.school_id)

    try:
        user = db.query(User).filter(User.id == teacher.user_id).first()
        if user:
            user.activation = StatusEnum.INACTIVE
        db.delete(teacher)
        db.commit()
        return {"success": True, "message": "Teacher separated/deactivated successfully"}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process teacher separation") from exc

# ==========================================
# 2. ADD LAB ASSISTANT
# ==========================================

@router.post('/add-lab-assistant', status_code=status.HTTP_201_CREATED)
def add_lab_assistant(payload: LabAssistantCreateRequest,
                      db: Session = Depends(get_db),
                      curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, payload.school_id)
    
    existing = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="User email already registered")

    temp_pass = get_random_pass()
    try:
        user = User(
            school_id=payload.school_id,
            name=payload.name,
            email=payload.email.strip().lower(),
            password=hash_password(temp_pass),
            role="LAB_ASSISTANT",
            phonenumber=payload.phone,
            activation=StatusEnum.ACTIVE
        )
        db.add(user)
        db.flush()

        lab = Lab(
            school_id=payload.school_id,
            lab_name=payload.lab_name,
            lab_assistant_id=user.id,
            activation=StatusEnum.ACTIVE
        )
        db.add(lab)
        db.commit()
        return {"success": True, "message": "Lab assistant added and assigned to lab successfully", "user_id": user.id, "lab_id": lab.id}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to add lab assistant") from exc

# ==========================================
# 3. ADD STUDENT
# ==========================================

@router.post('/add-student', status_code=status.HTTP_201_CREATED)
def add_student(payload: StudentCreateRequest,
                db: Session = Depends(get_db),
                curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, payload.school_id)

    try:
        student = Student(
            school_id=payload.school_id,
            class_id=payload.class_id,
            section_id=payload.section_id,
            role_no=payload.roll_no,
            name=payload.name,
            parents_name=payload.parents_name,
            parentes_pn_no=payload.parents_phone,
            activation=StatusEnum.ACTIVE
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        return {"success": True, "message": "Student registered successfully", "student_id": student.id}
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Student roll number conflict or invalid reference") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not add student") from exc

# ==========================================
# 4. ADD CLASS, SECTION & SUBJECT
# ==========================================

@router.post('/add-class', status_code=status.HTTP_201_CREATED)
def add_class(payload: ClassCreateRequest,
              db: Session = Depends(get_db),
              curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, payload.school_id)

    try:
        class_obj = ClassModel(
            school_id=payload.school_id,
            class_name=payload.class_name,
            grade_level=payload.grade_level,
            activation_status=StatusEnum.ACTIVE
        )
        db.add(class_obj)
        db.commit()
        db.refresh(class_obj)
        return {"success": True, "message": "Class added successfully", "class_id": class_obj.id}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create class") from exc

@router.post('/add-section', status_code=status.HTTP_201_CREATED)
def add_section(payload: SectionCreateRequest,
                db: Session = Depends(get_db),
                curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    
    class_obj = db.query(ClassModel).filter(ClassModel.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    
    authorize_school(db, curr, class_obj.school_id)

    try:
        section = ClassSection(
            class_id=payload.class_id,
            section_name=payload.section_name,
            activation=StatusEnum.ACTIVE
        )
        db.add(section)
        db.commit()
        db.refresh(section)
        return {"success": True, "message": "Section added successfully", "section_id": section.id}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create section") from exc

@router.post('/add-subject', status_code=status.HTTP_201_CREATED)
def add_subject(payload: SubjectCreateRequest,
                db: Session = Depends(get_db),
                curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, payload.school_id)
    class_obj = db.query(ClassModel).filter(ClassModel.id == payload.class_id, ClassModel.school_id == payload.school_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found in this school")

    try:
        subject = Subject(
            school_id=payload.school_id,
            class_id=payload.class_id,
            subject_name=payload.subject_name,
            activation=StatusEnum.ACTIVE
        )
        db.add(subject)
        db.commit()
        db.refresh(subject)
        return {"success": True, "message": "Subject assigned and added to class successfully", "subject_id": subject.id}
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not add subject") from exc

# ==========================================
# 5. CLASS SCHEDULING (Schedule to Teacher)
# ==========================================
@router.post('/schedule-class', status_code=status.HTTP_201_CREATED)
def schedule_class_to_teacher(payload: ClassScheduleRequest,
                              db: Session = Depends(get_db),
                              curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    
    # 1. Authorize School Access
    authorize_school(db, curr, payload.school_id)

    # 2. Validate Class belongs to the specified School
    class_obj = db.query(ClassModel).filter(
        ClassModel.id == payload.class_id,
        ClassModel.school_id == payload.school_id
    ).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found or does not belong to this school")

    # 3. Validate Section belongs to the specified Class
    section_obj = db.query(ClassSection).filter(
        ClassSection.id == payload.section_id,
        ClassSection.class_id == payload.class_id
    ).first()
    if not section_obj:
        raise HTTPException(status_code=404, detail="Section not found or does not belong to this class")

    # 4. Validate Subject belongs to both the School and the Class
    subject_obj = db.query(Subject).filter(
        Subject.id == payload.subject_id,
        Subject.school_id == payload.school_id,
        Subject.class_id == payload.class_id
    ).first()
    if not subject_obj:
        raise HTTPException(status_code=404, detail="Subject not found or does not belong to this class/school")

    # 5. Validate Teacher exists, has TEACHER role, and belongs to this School
    teacher_user = db.query(User).filter(
        User.id == payload.teacher_id,
        User.role == Role.TEACHER,
        User.school_id == payload.school_id
    ).first()
    if not teacher_user:
        raise HTTPException(status_code=404, detail="Teacher not found or does not belong to this school")

    # 6. Edge Case: Check for Teacher Time-Slot Conflict (Double Booking)
    existing_schedule = db.query(ClassScheduler).filter(
        ClassScheduler.teacher_id == payload.teacher_id,
        ClassScheduler.class_schedule == payload.class_schedule
    ).first()
    if existing_schedule:
        raise HTTPException(status_code=409, detail="Teacher is already scheduled for another class at this exact time slot")

    # 7. Commit Schedule Entry
    try:
        scheduler = ClassScheduler(
            school_id=payload.school_id,
            class_id=payload.class_id,
            section_id=payload.section_id,
            subject_id=payload.subject_id,
            teacher_id=payload.teacher_id,
            class_schedule=payload.class_schedule
        )
        db.add(scheduler)
        db.commit()
        db.refresh(scheduler)
        
        return {
            "success": True,
            "message": "Class scheduled to teacher successfully",
            "schedule_id": scheduler.id
        }
        
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not schedule class due to a database error") from exc



@router.get("/download-template", response_model=None, summary="Download Teacher Bulk Upload Excel Template")
async def download_teacher_template(curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    data = {
        "Full Name": ["Anita Devi", "Raj Kumar"],
        "Email": ["anita.devi@sunrise.edu.in", "raj.kumar@sunrise.edu.in"],
        "Phone": ["9876543210", "9876543211"],
        "Subject": ["Science", "Mathematics"],
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


@router.post('/bulk-upload', status_code=status.HTTP_200_OK)
def bulk_upload_teachers(school_id: int = Form(...), file: UploadFile = File(...),
                         db: Session = Depends(get_db),
                         curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    school = authorize_school(db, curr, school_id)
    
    if not file.filename or not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(status_code=400, detail='Only .xlsx files are supported')
    
    content = file.file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='Excel file exceeds 5 MB')
    
    try:
        df = pd.read_excel(io.BytesIO(content), engine='openpyxl', dtype=str)
    except Exception:
        raise HTTPException(status_code=400, detail='Invalid Excel file')
        
    required = {'Full Name', 'Email', 'Phone', 'Subject', 'Status'}
    if not required.issubset(df.columns):
        raise HTTPException(status_code=422, detail=f'Missing columns: {sorted(required - set(df.columns))}')
        
    if len(df) > 1000:
        raise HTTPException(status_code=413, detail='Maximum 1000 rows per upload')
        
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
                
            phone = str(row['Phone']).strip() if pd.notna(row['Phone']) else None
            
            # Check duplicate in DB
            if db.query(User).filter(User.email == email).first():
                raise ValueError('Email already exists in database')

            temp_password = get_random_pass()
            user = User(
                school_id=school_id,
                name=name,
                email=email,
                phonenumber=phone,
                password=hash_password(temp_password),
                role=Role.TEACHER,
                activation=StatusEnum.ACTIVE if state == 'active' else StatusEnum.INACTIVE
            )
            db.add(user)
            db.flush()

            teacher = Teacher(
                user_id=user.id,
                school_id=school_id
            )
            db.add(teacher)
            db.commit()
            successes += 1
            
            # Safe email send notification
            try:
                send_teacher_welcome_email(
                    to_email=email,
                    teacher_name=name,
                    temp_password=temp_password,
                    school_obj=school
                )
            except Exception:
                pass

        except (ValueError, ValidationError, IntegrityError, SQLAlchemyError) as exc:
            db.rollback()
            failures.append({
                'row': row_number, 
                'email': email, 
                'error': 'Database conflict' if isinstance(exc, IntegrityError) else str(exc)
            })
            
    return {
        'total_rows_processed': len(df),
        'success_count': successes,
        'failure_count': len(failures),
        'failed_rows': failures
    }




# ==========================================
# SCHOOL ADMIN RETRIEVAL (GET) ENDPOINTS
# ==========================================

@router.get('/teachers/all', summary="Get all teachers with all assigned classes and details")
def get_all_teachers_detailed(school_id: int, db: Session = Depends(get_db),
                             curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, school_id)
    teachers = db.query(User).filter(User.role == Role.TEACHER, User.school_id == school_id).all()
    
    result = []
    for t in teachers:
        teacher_profile = db.query(Teacher).filter(Teacher.user_id == t.id).first()
        schedules = db.query(ClassScheduler).filter(ClassScheduler.teacher_id == t.id, ClassScheduler.school_id == school_id).all()
        
        assigned_classes = []
        seen_assignments = set()
        
        # Collect assignments from ClassScheduler
        for sched in schedules:
            cls_name = sched.class_obj.class_name if sched.class_obj else None
            sec_name = sched.section.section_name if sched.section else None
            subj_name = sched.subject.subject_name if sched.subject else None
            key = (sched.class_id, sched.section_id, sched.subject_id)
            if key not in seen_assignments:
                seen_assignments.add(key)
                assigned_classes.append({
                    "class_id": sched.class_id,
                    "class_name": cls_name,
                    "section_id": sched.section_id,
                    "section_name": sec_name,
                    "subject_id": sched.subject_id,
                    "subject_name": subj_name
                })
        
        # Include primary assignment from Teacher model if present
        if teacher_profile and teacher_profile.class_id:
            cls_name = teacher_profile.class_obj.class_name if teacher_profile.class_obj else None
            sec_name = teacher_profile.section_obj.section_name if teacher_profile.section_obj else None
            subj_name = teacher_profile.subject_obj.subject_name if teacher_profile.subject_obj else None
            key = (teacher_profile.class_id, teacher_profile.section, teacher_profile.subject)
            if key not in seen_assignments and (cls_name or subj_name):
                assigned_classes.append({
                    "class_id": teacher_profile.class_id,
                    "class_name": cls_name,
                    "section_id": teacher_profile.section,
                    "section_name": sec_name,
                    "subject_id": teacher_profile.subject,
                    "subject_name": subj_name
                })

        result.append({
            "user_id": t.id,
            "name": t.name,
            "email": t.email,
            "phone": t.phonenumber,
            "activation_status": t.activation.value if hasattr(t.activation, 'value') else t.activation,
            "primary_subject": t.subject,
            "assigned_classes": assigned_classes
        })
    return {"success": True, "count": len(result), "teachers": result}


@router.get('/lab-assistants/all', summary="Get all lab assistants with lab details and status")
def get_all_lab_assistants(school_id: int, db: Session = Depends(get_db),
                           curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, school_id)
    labs = db.query(Lab).filter(Lab.school_id == school_id).all()
    
    result = []
    for lab in labs:
        assistant = db.query(User).filter(User.id == lab.lab_assistant_id).first() if lab.lab_assistant_id else None
        result.append({
            "lab_id": lab.id,
            "lab_name": lab.lab_name,
            "lab_status": lab.activation.value if hasattr(lab.activation, 'value') else lab.activation,
            "lab_time": lab.lab_time,
            "assistant": {
                "user_id": assistant.id if assistant else None,
                "name": assistant.name if assistant else None,
                "email": assistant.email if assistant else None,
                "phone": assistant.phonenumber if assistant else None,
                "status": assistant.activation.value if assistant and hasattr(assistant.activation, 'value') else (assistant.activation if assistant else None)
            } if assistant else None
        })
    return {"success": True, "count": len(result), "lab_assistants": result}


@router.get('/students/all', summary="Get all students with roll, name, class, section, parents name, phone, and status")
def get_all_students(school_id: int, db: Session = Depends(get_db),
                     curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, school_id)
    students = db.query(Student).filter(Student.school_id == school_id).all()
    
    result = []
    for s in students:
        result.append({
            "student_id": s.id,
            "roll_no": s.role_no,
            "name": s.name,
            "class_name": s.class_obj.class_name if s.class_obj else None,
            "section_name": s.section.section_name if s.section else None,
            "parents_name": s.parents_name,
            "parents_phone": s.parentes_pn_no,
            "status": s.activation.value if hasattr(s.activation, 'value') else s.activation
        })
    return {"success": True, "count": len(result), "students": result}


@router.get('/classes/all', summary="Get all classes with name, grade level, total sections, total students, and status")
def get_all_classes(school_id: int, db: Session = Depends(get_db),
                    curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, school_id)
    classes = db.query(ClassModel).filter(ClassModel.school_id == school_id).all()
    
    result = []
    for c in classes:
        total_sections = len(c.sections) if c.sections else 0
        total_students = len(c.students) if c.students else 0
        result.append({
            "class_id": c.id,
            "class_name": c.class_name,
            "grade_level": c.grade_level,
            "total_sections": total_sections,
            "total_students": total_students,
            "status": c.activation_status.value if hasattr(c.activation_status, 'value') else c.activation_status
        })
    return {"success": True, "count": len(result), "classes": result}


@router.get('/sections/all', summary="Get all sections with name, class name, total students, and status")
def get_all_sections(school_id: int, db: Session = Depends(get_db),
                     curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, school_id)
    
    sections = db.query(ClassSection).join(ClassModel, ClassSection.class_id == ClassModel.id)\
                 .filter(ClassModel.school_id == school_id).all()
    
    result = []
    for sec in sections:
        total_students = len(sec.students) if sec.students else 0
        result.append({
            "section_id": sec.id,
            "section_name": sec.section_name,
            "class_name": sec.class_obj.class_name if sec.class_obj else None,
            "total_students": total_students,
            "status": sec.activation.value if hasattr(sec.activation, 'value') else sec.activation
        })
    return {"success": True, "count": len(result), "sections": result}


@router.get('/subjects/all', summary="Get all subjects with name, classes, and status")
def get_all_subjects(school_id: int, db: Session = Depends(get_db),
                     curr: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.SUPER_ADMIN))):
    authorize_school(db, curr, school_id)
    subjects = db.query(Subject).filter(Subject.school_id == school_id).all()
    
    result = []
    for subj in subjects:
        class_name = subj.class_obj.class_name if subj.class_obj else None
        result.append({
            "subject_id": subj.id,
            "subject_name": subj.subject_name,
            "class_name": class_name,
            "status": subj.activation.value if hasattr(subj.activation, 'value') else subj.activation
        })
    return {"success": True, "count": len(result), "subjects": result}
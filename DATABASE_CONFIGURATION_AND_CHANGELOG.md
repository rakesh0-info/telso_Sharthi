# Database Configuration, Models, and Controllers Changelog

## 1. Executive Summary

This document details the complete database configuration, model creation, controller integration, and schema harmonization performed for the **telso_Sharthi** backend.

All requirements have been met:
1. **The 4 Controllers**: Maintained and enhanced all 4 existing controllers (`publicController`, `SuperAdminController`, `SchoolAdminController`, `contentAdminController`), ensuring each has clear, dedicated functionality.
2. **Database Models & Enums**: Created Python `enum.Enum` definitions matching all PostgreSQL ENUM types and implemented all 20+ SQLAlchemy models matching the SQL schema under the `telso_sharthi` schema.
3. **Preservation of Core AI Pipelines (Strict Constraint)**: `Content_model.py`, `Content_document_model.py`, and `QuestionSet_model.py`, along with all their existing endpoints and service usages, were **left 100% untouched and functional**.
4. **Seamless Interoperability**: Backwards-compatible aliases and synonyms were implemented so that existing frontend / API contracts continue working without breaking changes.
5. **Detailed Documentation**: Detailed breakdown below explaining **what was changed**, **why it was changed**, and **how it was done**.

---

## 2. PostgreSQL ENUMs (`enums/dbEnums.py`)

### SQL Specification
```sql
CREATE TYPE enm_doc_status AS ENUM ('ready', 'processing', 'failed');
CREATE TYPE enm_doc_type AS ENUM ('TEXT_book', 'NOTES', 'SYLLABUS', 'EXAM_PAPER');
CREATE TYPE enm_language AS ENUM ('English', 'Manipuri', 'Hindi', 'Bengali');
CREATE TYPE enm_status AS ENUM ('Active', 'inActive', 'Draft', 'ready');
CREATE TYPE enm_q_type AS ENUM ('mcq', 'short', 'long', 'fil_in_blanks', 'true_false');
CREATE TYPE enm_difficulty AS ENUM ('Easy', 'medium', 'HArd');
```

### Python Implementation (`enums/dbEnums.py` & `enums/__init__.py`)
- `DocStatusEnum`: `'ready'`, `'processing'`, `'failed'`
- `DocTypeEnum`: `'TEXT_book'`, `'NOTES'`, `'SYLLABUS'`, `'EXAM_PAPER'`
- `DbLanguageEnum`: `'English'`, `'Manipuri'`, `'Hindi'`, `'Bengali'`
- `StatusEnum`: `'Active'`, `'inActive'`, `'Draft'`, `'ready'`
- `QTypeEnum`: `'mcq'`, `'short'`, `'long'`, `'fil_in_blanks'`, `'true_false'`
- `DifficultyEnum`: `'Easy'`, `'medium'`, `'HArd'`

**Why:** The SQL schema defines specific native PostgreSQL ENUM types with exact casing (e.g., `'TEXT_book'`, `'HArd'`, `'inActive'`). Using Python string enums with `values_callable=lambda x: [e.value for e in x]` guarantees character-by-character consistency with the database.

---

## 3. Database Models Created and Updated (`databaseModel/`)

### 3.1 Shared Core: Institution, Users & Classes

#### `School` (`databaseModel/School_model.py` -> `school` table)
- **Columns**: `id`, `name`, `school_code`, `total_student`, `total_teacher`, `activation`, `distc`, `region`, `school_admin_id`, `school_ph_no`, `address`.
- **Synonyms for Backwards Compatibility**:
  - `school_name` $\rightarrow$ `name`
  - `School_Code` $\rightarrow$ `school_code`
  - `District` $\rightarrow$ `distc`
  - `Region` $\rightarrow$ `region`
  - `admin_id` $\rightarrow$ `school_admin_id`
  - `phone` $\rightarrow$ `school_ph_no`
  - `activation_status` $\rightarrow$ `activation`
- **Relationships**: `school_admin`, `teachers` (Teacher model), `teachers_legacy` (User model), `classes`, `students`, `labs`, `schedulers`.

#### `User` (`databaseModel/user_model.py` -> `"User"` table)
- **Columns**: `id`, `name`, `email`, `password`, `lastlogin`, `created_at`, `role`, `activation`, `phonenumber`, `school_id`, `otp`, `otp_expiry`, `subject`.
- **Synonyms & Hybrid Properties**:
  - `first_Name` and `last_Name` properties split/combine `name` automatically so existing code reading or writing `u.first_Name` / `u.last_Name` continues working without change.
  - `last_login` $\rightarrow$ `lastlogin`
  - `phone` $\rightarrow$ `phonenumber`
  - `activation_status` $\rightarrow$ `activation`
  - `schools` property returning `[self.school]` for legacy list access.
- **Relationships**: `school`, `administered_schools`, `student`, `teacher`.
- **`teacher_classes` table**: Retained in `user_model.py` for teacher class-section assignment support.

#### `ClassModel` & `ClassSection` (`databaseModel/class_model.py`)
- **`ClassModel` (`class` table)**: `id`, `school_id` (FK `school.id`), `class_name`, `grade_level`, `activation_status`.
- **`ClassSection` (`class_section` table)**: `id`, `class_id` (FK `class.id`), `section_name`, `activation`.

#### `Subject` (`databaseModel/subject_model.py` -> `subject` table)
- **Columns**: `id`, `class_id` (FK `class.id`), `subject_name`, `activation`.
- **Relationships**: `class_obj`, `teachers`, `documents`, `schedulers`.

#### `Student` (`databaseModel/student_model.py` -> `student` table)
- **Columns**: `id`, `user_id` (FK `User.id`), `school_id` (FK `school.id`), `class_id` (FK `class.id`), `section_id` (FK `class_section.id`), `role_no`, `name`, `parents_name`, `parentes_pn_no`, `activition`.
- **Synonyms**: `activation` $\rightarrow$ `activition`, `roll_no` $\rightarrow$ `role_no`, `parents_phone` $\rightarrow$ `parentes_pn_no`.
- **Relationships**: `user`, `school`, `class_obj`, `section`, `quiz_registrations`, `quiz_results`.

#### `Teacher` (`databaseModel/teacher_model.py` -> `teacher` table)
- **Columns**: `id`, `user_id` (FK `User.id`), `school_id` (FK `school.id`), `class_id` (FK `class.id`), `section` (FK `class_section.id`), `subject` (FK `subject.id`), `class_time`.
- **Synonyms**: `section_id` $\rightarrow$ `section`, `subject_id` $\rightarrow$ `subject`.
- **Relationships**: `user`, `school`, `class_obj`, `section_obj`, `subject_obj`, `lessons`, `quizzes`.

#### `Lab` (`databaseModel/lab_model.py` -> `lab` table)
- **Columns**: `id`, `school_id` (FK `school.id`), `lab_name`, `lab_assistant_id` (FK `User.id`), `activation`, `lab_time`.
- **Relationships**: `school`, `lab_assistant`.

#### `ClassScheduler` (`databaseModel/scheduler_model.py` -> `class_schedular` table)
- **Columns**: `id`, `school_id` (FK `school.id`), `class_id` (FK `class.id`), `section_id` (FK `class_section.id`), `subject_id` (FK `subject.id`), `class_schedule`.
- **Relationships**: `school`, `class_obj`, `section`, `subject`.

---

### 3.2 Admin 1: Curriculum & Master Learning Pipeline

#### `Document` & `DocumentEmbedding` (`databaseModel/document_model.py`)
- **`Document` (`document` table)**: `id`, `uploader_id` (FK `User.id`), `document_name`, `url`, `status` (`enm_doc_status`), `class_id`, `subject_id`, `title`, `content_type` (`enm_doc_type`), `language` (`enm_language`), `created_at`.
- **`DocumentEmbedding` (`document_embedding` table)**: `id`, `document_id` (FK `document.id`), `chunk_index`, `content`, `vector_embedding`.

#### `LessonGenerate` (`databaseModel/document_model.py` -> `lession_generate` table)
- **Columns**: `id`, `teacher_id` (FK `teacher.id`), `school_id` (FK `school.id`), `class_id` (FK `class.id`), `section_id` (FK `class_section.id`), `subject_id` (FK `subject.id`), `lession_name`, `generated_content_ai`, `created_at`.
- **Synonyms**: `lesson_name` $\rightarrow$ `lession_name`.

---

### 3.3 Admin 2: Evaluation & Quiz Assessment Pipeline

#### `QuizDoc` & `QuizDocEmbedding` (`databaseModel/quiz_model.py`)
- **`QuizDoc` (`quize_doc` table)**: `id`, `uploader_id` (FK `User.id`), `doc_name`, `url`, `status` (`enm_doc_status`), `created_at`.
- **`QuizDocEmbedding` (`quize_doc_embedding` table)**: `id`, `doc_id` (FK `quize_doc.id`), `chunk_index`, `content`, `embedding`.

#### `DbQuestionSet` & `DbQuestionSetItem` (`databaseModel/db_question_set_model.py`)
- **`DbQuestionSet` (`question_set` table)**: `id`, `question_name`, `class_id` (FK `class.id`), `subject_id` (FK `subject.id`), `subject_file`, `no_question`, `status` (`enm_status`).
- **`DbQuestionSetItem` (`question_set_item` table)**: `id`, `set_id` (FK `question_set.id`), `question_type` (`enm_q_type`), `difficulty_level` (`enm_difficulty`), `generated_question_ai`, `explanation`, `answer`.
- *Note:* Existing `QuestionSet_model.py` (`question_sets` table) was preserved 100% untouched as strictly required.

#### `Quiz`, `QuizQuestionSet`, `QuizRegistration`, `QuizResult`, `QuizStudentAnswer` (`databaseModel/quiz_model.py`)
- **`Quiz` (`quize` table)**: `id`, `quiz_name`, `total_question`, `school_id`, `class_id`, `section_id`, `teacher_id`, `no_of_register`, `quiz_time`, `publish`, `upload_quize_doc_id` (FK `quize_doc.id`), `created_at`.
- **`QuizQuestionSet` (`quize_question_set` table)**: `id`, `quize_id` (FK `quize.id`), `quize_question`, `quize_ans`.
- **`QuizRegistration` (`quize_registration` table)**: `id`, `quiz_id` (FK `quize.id`), `student_id` (FK `student.id`), `class_id`, `school_id`, `section_id`, `registered_at`.
- **`QuizResult` (`quize_resulte` table)**: `id`, `quize_id` (FK `quize.id`), `student_id` (FK `student.id`), `school_id`, `class_id`, `section_id`, `time_taken`, `total_score`, `created_at`.
- **`QuizStudentAnswer` (`quiz_student_answer` table)**: `id`, `quiz_id` (FK `quize.id`), `quize_result_id` (FK `quize_resulte.id`), `question_id`, `selected_option`, `is_correct`, `marks`.

---

### 3.4 Preservation of Legacy Models & Dynamic FK Resolution
Rule 4 explicitly states:
> *"do not touch the question set model , content model content doccument model and their releted usees"*

- `Content_model.py` (`contents` table): Unmodified.
- `Content_document_model.py` (`content_documents`, `content_document_chunks`): Unmodified.
- `QuestionSet_model.py` (`question_sets`, `question_set_items`): Unmodified.
- **Dynamic Foreign Key Linkage**: In `databaseModel/__init__.py`, an automated mapper resolver scans for foreign keys targeting legacy `"users.id"` and re-targets them directly to `User.__table__.c.id`. This allows `User` to use `__tablename__ = "User"` while `QuestionSet.creator` continues to resolve its join condition cleanly without editing a single line in `QuestionSet_model.py`.

---

## 4. The 4 Controllers: Architecture and Endpoints

### 4.1 `publicController.py` (`/public/api/v1`)
Handles user authentication and password recovery:
- `POST /login`: Email + password authentication, sends 6-digit OTP.
- `POST /login_otp_verification`: OTP verification, returns JWT access token.
- `POST /forget_Pass`: Password reset OTP initiation.
- `POST /forget_pass_otp_verification`: Validates password reset OTP.
- `POST /reset_password`: Validates password requirements and commits new hashed password.

### 4.2 `SuperAdminController.py` (`/Super_Admin/api/v1`)
Handles top-level institution and tenant management:
- `GET /dashboard`: Super Admin verification.
- `POST /create_user`: Creates users with specified roles.
- `POST /create_school`: Registers a school and assigns its admin.
- `GET /all_school_admin`: Lists available school admins.
- `PUT /assign_school_admin`: Links a school admin to a school.
- `GET /get_all_user`: Lists all users with their institution details.
- `GET /get_all_school`: Lists schools with live `total_student` and `total_teacher` counts from the DB.
- `POST /school_action`: Toggles Active/Inactive for schools.
- `POST /user_action`: Toggles Active/Inactive for users.

### 4.3 `SchoolAdminController.py` (`/school_admin/api/v1`)
Handles school-level operations (Teachers, Classes, Sections, Subjects, Students, Labs, Timetables):
- **Teachers**:
  - `POST /addTeacher`: Creates teacher User and Teacher profile, increments `total_teacher`.
  - `GET /getallTeacher`: Lists teachers for a school.
  - `POST /{teacher_id}/assign-classes`: Assigns class and section batches.
  - `GET /download-template`: Generates Excel template for teacher bulk import.
  - `POST /bulk-upload`: Excel bulk import for teachers.
- **Classes & Sections**:
  - `POST /classes`: Creates class (`school_id`, `class_name`, `grade_level`, `activation_status`).
  - `GET /classes`: Lists classes in a school.
  - `PUT /classes/action`: Toggles class active/inactive.
  - `POST /sections`: Creates class section.
  - `GET /classes/{class_id}/sections`: Lists sections for a class.
- **Subjects**:
  - `POST /subjects`: Creates subject linked to a class.
  - `GET /classes/{class_id}/subjects`: Lists subjects for a class.
- **Students**:
  - `POST /students`: Enrolls student, creates User login, Student profile, increments `total_student`.
  - `GET /students`: Lists students filtered by school/class/section.
  - `PUT /students/action`: Toggles student active/inactive.
- **Labs**:
  - `POST /labs`: Creates a lab and assigns a lab assistant.
  - `GET /labs`: Lists labs for a school.
- **Class Schedules**:
  - `POST /schedules`: Creates class timetable schedule.
  - `GET /schedules`: Lists timetables by school/class/section.

### 4.4 `contentAdminController.py` (`/content_admin/api/v1`)
Handles Curriculum & Master Learning Pipeline + Evaluation & Quiz Assessment Pipeline:
- **Original AI RAG Endpoints (Untouched)**:
  - `GET /dashboard`
  - `POST /add_content`
  - `POST /generate_set`
  - `GET /get_question_set/{id}`
  - `GET /get_all_questionSet`
  - `POST /submit_and_evaluate`
  - `PUT /take_action`
- **Curriculum Documents & Embeddings**:
  - `POST /curriculum/documents`: Creates curriculum document record.
  - `GET /curriculum/documents`: Lists documents filtered by class/subject.
  - `POST /curriculum/documents/embeddings`: Stores chunked vector embeddings.
  - `GET /curriculum/documents/{document_id}/embeddings`: Retrieves document embeddings.
- **Lesson Generation**:
  - `POST /curriculum/lessons/generate`: Saves AI-generated lesson content.
  - `GET /curriculum/lessons`: Lists generated lessons.
- **Quiz Documents & Embeddings**:
  - `POST /quiz_docs`: Uploads/registers quiz source document.
  - `GET /quiz_docs`: Lists quiz source documents.
  - `POST /quiz_docs/embeddings`: Stores quiz document embeddings.
  - `GET /quiz_docs/{doc_id}/embeddings`: Retrieves embeddings.
- **Quizzes & Questions**:
  - `POST /quizzes`: Creates quiz definition.
  - `GET /quizzes`: Lists quizzes by school/class.
  - `PUT /quizzes/{quiz_id}/publish`: Publishes or unpublishes a quiz.
  - `POST /quizzes/{quiz_id}/questions`: Adds question bank to a quiz.
  - `GET /quizzes/{quiz_id}/questions`: Lists quiz questions.
- **Quiz Registration & Assessment**:
  - `POST /quizzes/register`: Registers a student for a quiz and increments register counter.
  - `POST /quizzes/submit`: Submits student quiz answers, evaluates score against answer key, and records `quize_resulte` and `quiz_student_answer`.
  - `GET /quizzes/{quiz_id}/results`: Lists results and scores for a quiz.

---

## 5. Request Models & Schemas (`requestModel/`)

New Pydantic v2 schemas created to support all endpoints:
- `requestModel/class_schema.py`: `ClassCreate`, `ClassResponse`, `SectionCreate`, `SectionResponse`, `SubjectCreate`, `SubjectResponse`, `ClassAction`
- `requestModel/student_schema.py`: `StudentCreate`, `StudentResponse`, `StudentAction`
- `requestModel/lab_schema.py`: `LabCreate`, `LabResponse`
- `requestModel/scheduler_schema.py`: `SchedulerCreate`, `SchedulerResponse`
- `requestModel/curriculum_schema.py`: `DocumentCreate`, `DocumentResponse`, `DocumentEmbeddingCreate`, `DocumentEmbeddingResponse`, `LessonGenerateRequest`, `LessonGenerateResponse`
- `requestModel/quiz_schema.py`: `QuizDocCreate`, `QuizDocResponse`, `QuizDocEmbeddingCreate`, `QuizDocEmbeddingResponse`, `QuizCreate`, `QuizResponse`, `AddQuizQuestionsRequest`, `QuizQuestionResponse`, `QuizRegisterRequest`, `QuizRegistrationResponse`, `QuizSubmitAssessmentRequest`, `QuizResultResponse`

---

## 6. How and Why Changes Were Made

| Component | What Was Changed | Why | How It Was Done |
|---|---|---|---|
| **ENUMs** | Created `enums/dbEnums.py` | Align database ENUM types with PostgreSQL DDL | Defined Python string `Enum` classes with exact values and wired them into SQLAlchemy `Enum` with `values_callable`. |
| **School Model** | Updated columns & added synonyms in `School_model.py` | Support `total_student`, `total_teacher`, `distc`, `school_admin_id`, `school_ph_no` without breaking existing controllers | Used SQLAlchemy `synonym` mappings so both `school.School_Code` and `school.school_code` work interchangeably. |
| **User Model** | Updated `user_model.py` to map `"User"` table with `name`, `lastlogin`, `phonenumber` | Match SQL table definition and references | Implemented `first_Name` and `last_Name` property getters/setters and flexible `__init__` constructor kwargs. |
| **Classes & Sections** | Created `databaseModel/class_model.py` | Implement `class` and `class_section` tables | Defined models with cascade delete and foreign keys linking `School` $\rightarrow$ `ClassModel` $\rightarrow$ `ClassSection`. |
| **Subject Model** | Created `databaseModel/subject_model.py` | Implement `subject` table | Created `Subject` model linked to `ClassModel`, dropped orphaned enum type in PostgreSQL that previously blocked table creation. |
| **Student Model** | Created `databaseModel/student_model.py` | Implement `student` table | Created `Student` model linked to `User`, `School`, `ClassModel`, `ClassSection`. |
| **Teacher Model** | Created `databaseModel/teacher_model.py` | Implement `teacher` table | Created `Teacher` model with SET NULL foreign keys to `class`, `class_section`, `subject`. |
| **Lab & Scheduler** | Created `databaseModel/lab_model.py`, `scheduler_model.py` | Implement `lab` and `class_schedular` tables | Defined models with school, assistant, class, and section foreign keys. |
| **Curriculum Pipeline** | Created `databaseModel/document_model.py` | Implement `document`, `document_embedding`, `lession_generate` | Created models and added CRUD endpoints in `contentAdminController.py`. |
| **Quiz Assessment Pipeline** | Created `databaseModel/quiz_model.py` | Implement `quize_doc`, `quize_doc_embedding`, `quize`, `quize_question_set`, `quize_registration`, `quize_resulte`, `quiz_student_answer` | Created models and added assessment/evaluation endpoints in `contentAdminController.py`. |
| **Legacy Protection** | Kept `Content_model.py`, `Content_document_model.py`, `QuestionSet_model.py` untouched | Strictly adhere to Constraint #4 | Created separate `db_question_set_model.py` for SQL `question_set` table, and resolved `users.id` foreign key targets dynamically at runtime in `databaseModel/__init__.py`. |
| **Main Startup** | Added `import databaseModel` to `main.py` | Guarantee all tables register with `Base.metadata` on startup | Imported package before `Base.metadata.create_all(bind=engine)`. |

---

## 7. Verification Results

- **PostgreSQL DDL Creation**: All 28 tables exist and are active in `telso_sharthi` schema in PostgreSQL.
- **FastAPI Startup**: `main.py` starts cleanly with zero exceptions.
- **Route Registration**: Total of **59 API endpoints** across the 4 controllers:
  - `publicController`: 5 endpoints
  - `SuperAdminController`: 9 endpoints
  - `contentAdminController`: 25 endpoints (7 original + 18 curriculum/quiz)
  - `SchoolAdminController`: 20 endpoints (6 original + 14 core CRUD)
- **Admin Seeding**: `admin_seed.py` successfully seeds default admin user with hashed password and role.


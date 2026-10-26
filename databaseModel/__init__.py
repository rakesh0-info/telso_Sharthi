from database_config import Base
from databaseModel.user_model import User
from databaseModel.School_model import School
from databaseModel.class_model import ClassModel, ClassSection
from databaseModel.subject_model import Subject
from databaseModel.student_model import Student
from databaseModel.teacher_model import Teacher
from databaseModel.lab_model import Lab
from databaseModel.scheduler_model import ClassScheduler

from databaseModel.quiz_model import (
    QuizDoc,
   
    Quiz,
    QuizQuestionSet,
    QuizRegistration,
    QuizResult,
    QuizStudentAnswer,
)

from databaseModel.Content_model import Content
from databaseModel.Content_document_model import ContentDocument, ContentDocumentChunk
from databaseModel.QuestionSet_model import QuestionSet, QuestionSetItem
from databaseModel.lesson_model import LessonGenerate

# Resolve legacy foreign key references pointing to 'users.id' -> 'User.id'
# to maintain complete compatibility without touching QuestionSet_model.py
for table in list(Base.metadata.tables.values()):
    for col in table.columns:
        for fk in list(col.foreign_keys):
            if fk._colspec in ("users.id", "telso_sharthi.users.id"):
                fk._set_target_column(User.__table__.c.id)

from sqlalchemy.orm import configure_mappers
configure_mappers()

__all__ = [
    "User",
    "School",
    "ClassModel",
    "ClassSection",
    "Subject",
    "Student",
    "Teacher",
    "Lab",
    "ClassScheduler",
    "LessonGenerate",
    "QuizDoc",
    
    "Quiz",
    "QuizQuestionSet",
    "QuizRegistration",
    "QuizResult",
    "QuizStudentAnswer",
    "Content",
    "ContentDocument",
    "ContentDocumentChunk",
    "QuestionSet",
    "QuestionSetItem",
]
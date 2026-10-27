from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Time,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, synonym
from pgvector.sqlalchemy import Vector
from database_config import Base
from enums.dbEnums import DocStatusEnum


class QuizDoc(Base):
    __tablename__ = "quize_doc"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uploader_id = Column(Integer, ForeignKey("User.id", ondelete="SET NULL"), nullable=True)
    school_id=Column(Integer,ForeignKey("school.id",ondelete="CASCADE"),nullable=False)
    class_id=Column(Integer,ForeignKey("class.id",ondelete="CASCADE"),nullable=False)
    doc_name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    status = Column(
        SQLEnum(
            DocStatusEnum,
            name="enm_doc_status",
            schema="telso_sharthi",
            inherit_schema=True,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=DocStatusEnum.READY,
        nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Synonyms
    document_name = synonym("doc_name")

    # Relationships
    uploader = relationship("User")
    # embeddings = relationship("QuizDocEmbedding", back_populates="quiz_doc", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="quiz_doc")


# class QuizDocEmbedding(Base):
#     __tablename__ = "quize_doc_embedding"

#     id = Column(Integer, primary_key=True, autoincrement=True)
#     doc_id = Column(Integer, ForeignKey("quize_doc.id", ondelete="CASCADE"), nullable=False)
#     chunk_index = Column(Integer, default=0, nullable=False)
#     content = Column(Text, nullable=False)
#     embedding = Column(Vector(3072), nullable=True)

#     # Relationships
#     quiz_doc = relationship("QuizDoc", back_populates="embeddings")


class Quiz(Base):
    __tablename__ = "quize"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_name = Column(String(255), nullable=False)
    total_question = Column(Integer, nullable=False)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("class_section.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subject.id", ondelete="CASCADE"), nullable=True) # <--- Added subject_id
    teacher_id = Column(Integer, ForeignKey("teacher.id", ondelete="CASCADE"), nullable=False)
    no_of_register = Column(Integer, default=0, nullable=False)
    quiz_time = Column(Integer, nullable=False)
    publish = Column(Boolean, default=False, nullable=False)
    is_start = Column(Boolean, default=False, nullable=False)
    upload_quize_doc_id = Column(Integer, ForeignKey("quize_doc.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    school = relationship("School")
    class_obj = relationship("ClassModel")
    section = relationship("ClassSection")
    subject = relationship("Subject") # <--- Added relationship
    teacher = relationship("Teacher", back_populates="quizzes")
    quiz_doc = relationship("QuizDoc", back_populates="quizzes")
    questions = relationship("QuizQuestionSet", back_populates="quiz", cascade="all, delete-orphan")
    registrations = relationship("QuizRegistration", back_populates="quiz", cascade="all, delete-orphan")
    results = relationship("QuizResult", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestionSet(Base):
    __tablename__ = "quize_question_set"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quize_id = Column(Integer, ForeignKey("quize.id", ondelete="CASCADE"), nullable=False)
    quize_question = Column(Text, nullable=False)
    quize_ans = Column(Text, nullable=False)

    # Synonyms
    quiz_id = synonym("quize_id")
    question = synonym("quize_question")
    answer = synonym("quize_ans")

    # Relationships
    quiz = relationship("Quiz", back_populates="questions")


class QuizRegistration(Base):
    __tablename__ = "quize_registration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(Integer, ForeignKey("quize.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("class_section.id", ondelete="CASCADE"), nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    quiz = relationship("Quiz", back_populates="registrations")
    student = relationship("Student", back_populates="quiz_registrations")
    class_obj = relationship("ClassModel")
    school = relationship("School")
    section = relationship("ClassSection")


class QuizResult(Base):
    __tablename__ = "quize_resulte"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quize_id = Column(Integer, ForeignKey("quize.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("student.id", ondelete="CASCADE"), nullable=False)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("class_section.id", ondelete="CASCADE"), nullable=False)
    time_taken = Column(Time, nullable=True)
    total_score = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('quize_id', 'student_id', name='uq_quiz_student_submission'),
    )

    # Synonyms
    quiz_id = synonym("quize_id")

    # Relationships
    quiz = relationship("Quiz", back_populates="results")
    student = relationship("Student", back_populates="quiz_results")
    school = relationship("School")
    class_obj = relationship("ClassModel")
    section = relationship("ClassSection")
    student_answers = relationship("QuizStudentAnswer", back_populates="quiz_result", cascade="all, delete-orphan")


class QuizStudentAnswer(Base):
    __tablename__ = "quiz_student_answer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(Integer, ForeignKey("quize.id", ondelete="CASCADE"), nullable=False)
    quize_result_id = Column(Integer, ForeignKey("quize_resulte.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, nullable=True)
    selected_option = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    marks = Column(Integer, default=0, nullable=False)

    # Synonyms
    result_id = synonym("quize_result_id")

    # Relationships
    quiz = relationship("Quiz")
    quiz_result = relationship("QuizResult", back_populates="student_answers")

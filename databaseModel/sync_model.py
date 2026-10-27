import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, UniqueConstraint
from database_config import Base

class SyncStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"

class LocalOfflineQuiz(Base):
    """Stores quizzes and questions downloaded from central server to local lab server."""
    __tablename__ = "local_offline_quizzes"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, unique=True, nullable=False, index=True)
    teacher_id = Column(Integer, nullable=False, index=True)
    subject_id = Column(Integer, nullable=False, index=True)
    school_id = Column(Integer, nullable=False, index=True)
    class_id = Column(Integer, nullable=False)
    section_id = Column(Integer, nullable=False)
    quiz_name = Column(String(255), nullable=False)
    total_questions = Column(Integer, nullable=False)
    quiz_time_minutes = Column(Integer, nullable=False)
    questions_json = Column(Text, nullable=False)  # Sanitized questions (answers stripped)
    is_start = Column(Integer, default=0)         # 0 = Not started, 1 = Running, 2 = Ended
    downloaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class LocalOfflineRegistration(Base):
    """Stores student registrations locally in the lab before syncing to central DB."""
    __tablename__ = "local_offline_registrations"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, nullable=False, index=True)
    student_id = Column(Integer, nullable=False, index=True)
    school_id = Column(Integer, nullable=False)
    class_id = Column(Integer, nullable=False)
    section_id = Column(Integer, nullable=False)
    sync_status = Column(Enum(SyncStatusEnum), default=SyncStatusEnum.PENDING, index=True)
    sync_error = Column(Text, nullable=True)
    synced_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('quiz_id', 'student_id', name='uq_offline_quiz_student_registration'),
    )

class LocalOfflineSubmission(Base):
    """Stores student answer submissions offline in the lab before syncing."""
    __tablename__ = "local_offline_submissions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, nullable=False, index=True)
    student_id = Column(Integer, nullable=False, index=True)
    school_id = Column(Integer, nullable=False)
    class_id = Column(Integer, nullable=False)
    section_id = Column(Integer, nullable=False)
    answers_json = Column(Text, nullable=False)
    time_taken_seconds = Column(Integer, nullable=True)
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sync_status = Column(Enum(SyncStatusEnum), default=SyncStatusEnum.PENDING, index=True)
    sync_error = Column(Text, nullable=True)
    synced_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('quiz_id', 'student_id', name='uq_offline_quiz_student_submission'),
    )
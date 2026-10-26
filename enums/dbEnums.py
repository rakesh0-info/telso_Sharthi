from enum import Enum


class DocStatusEnum(str, Enum):
    """Corresponds to PostgreSQL enm_doc_status."""
    READY = "ready"
    PROCESSING = "processing"
    FAILED = "failed"


class DocTypeEnum(str, Enum):
    """Corresponds to PostgreSQL enm_doc_type."""
    TEXT_BOOK = "TEXT_book"
    NOTES = "NOTES"
    SYLLABUS = "SYLLABUS"
    EXAM_PAPER = "EXAM_PAPER"


class DbLanguageEnum(str, Enum):
    """Corresponds to PostgreSQL enm_language."""
    ENGLISH = "English"
    MANIPURI = "Manipuri"
    HINDI = "Hindi"
    BENGALI = "Bengali"


class StatusEnum(str, Enum):
    """Corresponds to PostgreSQL enm_status."""
    ACTIVE = "Active"
    INACTIVE = "inActive"
    DRAFT = "Draft"
    READY = "ready"


class QTypeEnum(str, Enum):
    """Corresponds to PostgreSQL enm_q_type."""
    MCQ = "mcq"
    SHORT = "short"
    LONG = "long"
    FIL_IN_BLANKS = "fil_in_blanks"
    TRUE_FALSE = "true_false"


class DifficultyEnum(str, Enum):
    """Corresponds to PostgreSQL enm_difficulty."""
    EASY = "Easy"
    MEDIUM = "medium"
    HARD = "HArd"


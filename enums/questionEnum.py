from enum import Enum

class QuestionTypeEnum(str, Enum):
    MCQ = "MCQ"
    TRUE_FALSE = "True / False"
    SHORT_ANSWER = "Short Answer"
    LONG_ANSWER = "Long Answer"
    FILL_IN_BLANKS = "Fill in the Blanks"

class DifficultyEnum(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"

class QuestionSetStatusEnum(str, Enum):
    DRAFT = "Draft"
    READY = "Ready"
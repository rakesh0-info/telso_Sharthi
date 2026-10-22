from enum import Enum

class content_type(str,Enum):
    TEXT_BOOK="textbook"
    SYLLABUS="syllabus"
    NOTE="note"




class LanguageEnum(str, Enum):
    ENGLISH = "English"
    MANIPURI = "Manipuri"




class UploadStateEnum(str, Enum):
    NOT_START = "not start"
    READY = "ready"
    FAILED="failed"
   
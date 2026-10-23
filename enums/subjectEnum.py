from enum import Enum

class subject(str,Enum):
    SCIENCE="science"
    MATHEMATICE="Mathematices"
    PHYSICES="Physices"
    ALL_SUBJECT="All_subject"
    ENGLISH="english"
    MANIPURI="Manipuri"

class StudentClassEnum(str, Enum):
    VIII = "8"
    IX = "9"
    X = "10"
    XI = "11"
    XII = "12"

class StudentSectionEnum(str, Enum):
    CLASS_8A = "8A"
    CLASS_8B = "8B"
    CLASS_9A = "9A"
    CLASS_9B = "9B"
    CLASS_10A = "10A"
    CLASS_10B = "10B"
    
    
    

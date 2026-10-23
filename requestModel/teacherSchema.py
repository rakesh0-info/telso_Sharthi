from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator, field_validator
from enums.subjectEnum import StudentClassEnum, StudentSectionEnum

# These are GLOBAL rules. For per-school configurations use school-specific DB records.
CLASS_SECTIONS = {'8': {'8A','8B'}, '9': {'9A','9B'}, '10': {'10A','10B'}, '11': set(), '12': set()}

class ClassSectionAssignment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    class_name: StudentClassEnum
    section_name: Optional[StudentSectionEnum] = None

    @model_validator(mode='after')
    def check_pair(self):
        name = self.class_name.value
        section = self.section_name.value if self.section_name else None
        allowed = CLASS_SECTIONS.get(name)
        if allowed is None:
            raise ValueError(f'Class {name} is not configured')
        if allowed and section is None:
            raise ValueError(f'Class {name} requires a section: {sorted(allowed)}')
        if section is not None and section not in allowed:
            raise ValueError(f'Section {section} is not valid for class {name}; allowed: {sorted(allowed)}')
        return self

def validate_assignment_list(assignments: List[ClassSectionAssignment]):
    seen = set()
    for item in assignments:
        pair = (item.class_name.value, item.section_name.value if item.section_name else None)
        if pair in seen:
            raise ValueError(f'Duplicate class-section assignment: {pair}')
        seen.add(pair)
    return assignments

class TeacherCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    first_Name: str = Field(min_length=1, max_length=100)
    last_Name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    subjects: Optional[str] = None
    school_id: int = Field(gt=0)
    assignments: List[ClassSectionAssignment] = Field(default_factory=list, max_length=100)

    @field_validator('first_Name', 'last_Name')
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Name cannot be blank')
        return value

    @model_validator(mode='after')
    def check_assignments(self):
        validate_assignment_list(self.assignments)
        return self

class TeacherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_Name: str
    last_Name: str
    email: EmailStr
    phone: Optional[str] = None
    subjects: Optional[str] = None
    activation_status: str
    last_login: Optional[datetime] = None
    created_at: datetime
    assignments: List[ClassSectionAssignment] = Field(default_factory=list)

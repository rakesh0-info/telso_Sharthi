from typing import Optional
from pydantic import BaseModel, Field
from enums.dbEnums import StatusEnum


class ClassCreate(BaseModel):
    school_id: int = Field(..., gt=0)
    class_name: str = Field(..., min_length=1, max_length=100)
    grade_level: Optional[str] = Field(None, max_length=50)
    activation_status: StatusEnum = StatusEnum.ACTIVE


class ClassResponse(BaseModel):
    id: int
    school_id: int
    class_name: str
    grade_level: Optional[str] = None
    activation_status: str

    class Config:
        from_attributes = True


class SectionCreate(BaseModel):
    class_id: int = Field(..., gt=0)
    section_name: str = Field(..., min_length=1, max_length=50)
    activation: StatusEnum = StatusEnum.ACTIVE


class SectionResponse(BaseModel):
    id: int
    class_id: int
    section_name: str
    activation: str

    class Config:
        from_attributes = True


class SubjectCreate(BaseModel):
    class_id: int = Field(..., gt=0)
    subject_name: str = Field(..., min_length=1, max_length=150)
    activation: StatusEnum = StatusEnum.ACTIVE


class SubjectResponse(BaseModel):
    id: int
    class_id: int
    subject_name: str
    activation: str

    class Config:
        from_attributes = True


class ClassAction(BaseModel):
    class_id: int
    action_type: str  # 'active' or 'inactive'


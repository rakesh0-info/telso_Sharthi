from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from enums.dbEnums import StatusEnum


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6)
    school_id: int = Field(..., gt=0)
    class_id: int = Field(..., gt=0)
    section_id: int = Field(..., gt=0)
    role_no: str = Field(..., min_length=1, max_length=50)
    parents_name: Optional[str] = Field(None, max_length=255)
    parents_phone: Optional[str] = Field(None, max_length=20)
    activation: StatusEnum = StatusEnum.ACTIVE


class StudentResponse(BaseModel):
    id: int
    user_id: int
    school_id: int
    class_id: int
    section_id: int
    role_no: str
    name: str
    parents_name: Optional[str] = None
    parentes_pn_no: Optional[str] = None
    activition: str

    class Config:
        from_attributes = True


class StudentAction(BaseModel):
    student_id: int
    action_type: str  # 'active' or 'inactive'


from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enums.dbEnums import StatusEnum


class LabCreate(BaseModel):
    school_id: int = Field(..., gt=0)
    lab_name: str = Field(..., min_length=1, max_length=150)
    lab_assistant_id: Optional[int] = None
    activation: StatusEnum = StatusEnum.ACTIVE
    lab_time: Optional[datetime] = None


class LabResponse(BaseModel):
    id: int
    school_id: int
    lab_name: str
    lab_assistant_id: Optional[int] = None
    activation: str
    lab_time: Optional[datetime] = None

    class Config:
        from_attributes = True


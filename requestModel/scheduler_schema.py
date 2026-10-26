from datetime import datetime
from pydantic import BaseModel, Field


class SchedulerCreate(BaseModel):
    school_id: int = Field(..., gt=0)
    class_id: int = Field(..., gt=0)
    section_id: int = Field(..., gt=0)
    subject_id: int = Field(..., gt=0)
    class_schedule: datetime


class SchedulerResponse(BaseModel):
    id: int
    school_id: int
    class_id: int
    section_id: int
    subject_id: int
    class_schedule: datetime

    class Config:
        from_attributes = True


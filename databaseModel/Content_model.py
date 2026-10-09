from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime
from database_config import Base
from enums.contentEnum import content_type
from enums.subjectEnum import subject
from enums.contentEnum import LanguageEnum
from enums.contentEnum import UploadStateEnum

class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    content_type = Column(Enum(content_type), nullable=False)
    title = Column(String, nullable=False)
    language_type = Column(Enum(LanguageEnum), nullable=False)
    des = Column(String, nullable=True)
    class_name = Column(String, default="XII", nullable=False)
    subject = Column(Enum(subject), nullable=False)
    file_url = Column(String, nullable=True)
    file_upload_state = Column(Enum(UploadStateEnum), default=UploadStateEnum.NOT_START, nullable=False)
    last_update = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    update_by=Column(Integer,nullable=False)

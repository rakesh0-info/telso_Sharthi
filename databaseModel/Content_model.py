from datetime import datetime
from sqlalchemy import Column, ForeignKey, Integer, String, Enum, DateTime
from database_config import Base
from enums.contentEnum import content_type, LanguageEnum, UploadStateEnum

class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    content_type = Column(Enum(content_type, native_enum=False, create_type=False), nullable=False)
    title = Column(String, nullable=False)
    language_type = Column(Enum(LanguageEnum, native_enum=False, create_type=False), nullable=False)
    des = Column(String, nullable=True)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    subject = Column(Integer, ForeignKey("subject.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String, nullable=True)
    file_upload_state = Column(Enum(UploadStateEnum, native_enum=False, create_type=False), default=UploadStateEnum.NOT_START, nullable=False)
    last_update = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    update_by = Column(Integer, nullable=False)
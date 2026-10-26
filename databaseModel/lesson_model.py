from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, synonym
from database_config import Base


class LessonGenerate(Base):
    __tablename__ = "lession_generate"

    id = Column(Integer, primary_key=True, autoincrement=True)
    teacher_id = Column(Integer, ForeignKey("teacher.id", ondelete="CASCADE"), nullable=False)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("class_section.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subject.id", ondelete="CASCADE"), nullable=False)
    lession_name = Column(String(255), nullable=False)
    generated_content_ai = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Synonyms
    lesson_name = synonym("lession_name")

    # Relationships
    teacher = relationship("Teacher", back_populates="lessons")
    school = relationship("School")
    class_obj = relationship("ClassModel")
    section = relationship("ClassSection")
    subject = relationship("Subject")

    def __init__(self, **kwargs):
        if "lesson_name" in kwargs and "lession_name" not in kwargs:
            kwargs["lession_name"] = kwargs.pop("lesson_name")
        super().__init__(**kwargs)


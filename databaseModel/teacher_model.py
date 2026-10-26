from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, synonym
from database_config import Base


class Teacher(Base):
    __tablename__ = "teacher"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("User.id", ondelete="CASCADE"), nullable=False, unique=True)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="SET NULL"), nullable=True)
    section = Column(Integer, ForeignKey("class_section.id", ondelete="SET NULL"), nullable=True)
    subject = Column(Integer, ForeignKey("subject.id", ondelete="SET NULL"), nullable=True)
    class_time = Column(String(100), nullable=True)
   
    # Synonyms for standard naming
    section_id = synonym("section")
    subject_id = synonym("subject")

    # Relationships
    user = relationship("User", back_populates="teacher")
    school = relationship("School", back_populates="teachers")
    class_obj = relationship("ClassModel")
    section_obj = relationship("ClassSection")
    subject_obj = relationship("Subject", back_populates="teachers")
    lessons = relationship("LessonGenerate", back_populates="teacher", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="teacher", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "section_id" in kwargs and "section" not in kwargs:
            kwargs["section"] = kwargs.pop("section_id")
        if "subject_id" in kwargs and "subject" not in kwargs:
            kwargs["subject"] = kwargs.pop("subject_id")
        super().__init__(**kwargs)
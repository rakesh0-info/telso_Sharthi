from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database_config import Base


class ClassScheduler(Base):
    __tablename__ = "class_schedular"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("class_section.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subject.id", ondelete="CASCADE"), nullable=False)
    class_schedule = Column(DateTime, nullable=False)
    teacher_id=Column(Integer,ForeignKey("User.id",ondelete="CASCADE"),nullable=False)

    # Relationships
    school = relationship("School", back_populates="schedulers")
    class_obj = relationship("ClassModel", back_populates="schedulers")
    section = relationship("ClassSection", back_populates="schedulers")
    subject = relationship("Subject", back_populates="schedulers")


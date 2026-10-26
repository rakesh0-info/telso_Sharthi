from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from database_config import Base
from enums.dbEnums import StatusEnum


class Subject(Base):
    __tablename__ = "subject"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    subject_name = Column(String(150), nullable=False)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    activation = Column(
        SQLEnum(
            StatusEnum,
            name="enm_status",
            schema="telso_sharthi",
            inherit_schema=True,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=StatusEnum.ACTIVE,
        nullable=False
    )

    # Relationships
    school = relationship("School", back_populates="subjects")
    class_obj = relationship("ClassModel", back_populates="subjects")
    teachers = relationship("Teacher", back_populates="subject_obj")
    documents = relationship("ContentDocument", back_populates="subject_obj", cascade="all, delete-orphan")
    schedulers = relationship("ClassScheduler", back_populates="subject", cascade="all, delete-orphan")
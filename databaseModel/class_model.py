from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from database_config import Base
from enums.dbEnums import StatusEnum


class ClassModel(Base):
    __tablename__ = "class"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    class_name = Column(String(100), nullable=False)
    grade_level = Column(String(50), nullable=True)
    activation_status = Column(
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
    school = relationship("School", back_populates="classes")
    sections = relationship("ClassSection", back_populates="class_obj", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="class_obj", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="class_obj", cascade="all, delete-orphan")
    schedulers = relationship("ClassScheduler", back_populates="class_obj", cascade="all, delete-orphan")


class ClassSection(Base):
    __tablename__ = "class_section"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    section_name = Column(String(50), nullable=False)
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
    class_obj = relationship("ClassModel", back_populates="sections")
    students = relationship("Student", back_populates="section", cascade="all, delete-orphan")
    schedulers = relationship("ClassScheduler", back_populates="section", cascade="all, delete-orphan")


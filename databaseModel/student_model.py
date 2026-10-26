from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship, synonym
from database_config import Base
from enums.dbEnums import StatusEnum


class Student(Base):
    __tablename__ = "student"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("class.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("class_section.id", ondelete="CASCADE"), nullable=False)
    role_no = Column(String(50), nullable=False)  # Roll number used for student login
    name = Column(String(255), nullable=False)
    parents_name = Column(String(255), nullable=True)
    parentes_pn_no = Column(String(20), nullable=True)
    activition = Column(
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

    # Synonyms for convenience and typo tolerance
    activation = synonym("activition")
    roll_no = synonym("role_no")
    parents_phone = synonym("parentes_pn_no")

    # Relationships (Decoupled from User)
    school = relationship("School", back_populates="students")
    class_obj = relationship("ClassModel", back_populates="students")
    section = relationship("ClassSection", back_populates="students")
    quiz_registrations = relationship("QuizRegistration", back_populates="student", cascade="all, delete-orphan")
    quiz_results = relationship("QuizResult", back_populates="student", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "activation" in kwargs and "activition" not in kwargs:
            kwargs["activition"] = kwargs.pop("activation")
        if "roll_no" in kwargs and "role_no" not in kwargs:
            kwargs["role_no"] = kwargs.pop("roll_no")
        if "parents_phone" in kwargs and "parentes_pn_no" not in kwargs:
            kwargs["parentes_pn_no"] = kwargs.pop("parents_phone")
        super().__init__(**kwargs)
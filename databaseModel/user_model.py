from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Enum, DateTime,ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from database_config import Base
from enums.roleEnum import Role
from enums.userActivationEnum import activation


teacher_classes = Table(
    "teacher_classes",
    Base.metadata,

    Column(
        "id",
        Integer,
        primary_key=True,
        autoincrement=True
    ),

    Column(
        "user_id",
        Integer,
        ForeignKey(
            "telso_sharthi.users.id",
            ondelete="CASCADE"
        ),
        nullable=False
    ),

    Column(
        "class_name",
        String(10),
        nullable=False
    ),

    # Class may not have any section
    Column(
        "section_name",
        String(10),
        nullable=True
    ),

    UniqueConstraint(
        "user_id",
        "class_name",
        "section_name",
        name="uq_teacher_class_section"
    ),

    schema="telso_sharthi"

)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    first_Name = Column(String, nullable=False)
    last_Name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    school_id = Column(Integer, ForeignKey("school.id"), nullable=True)
    subject=Column(String(200),nullable=True)
    last_login = Column(DateTime, nullable=True)
    
    role = Column(
        Enum(Role, name="role", schema="telso_sharthi", inherit_schema=True),
        default=Role.USER,
        nullable=False
    )
    activation_status = Column(
        Enum(activation, name="activation_Status", schema="telso_sharthi", inherit_schema=True),
        default=activation.ACTIVE,
    )
    
    otp = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    administered_schools = relationship("School", foreign_keys="School.admin_id", back_populates="school_admin")
    school = relationship("School", foreign_keys=[school_id], back_populates="teachers")
    
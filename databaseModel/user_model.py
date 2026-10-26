from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Table,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship, synonym
from database_config import Base
from enums.roleEnum import Role
from enums.userActivationEnum import activation
from enums.dbEnums import StatusEnum


class User(Base):
    __tablename__ = "User"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    lastlogin = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    role = Column(String(50), nullable=False)
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
    phonenumber = Column(String(20), nullable=True)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=True)

    # Auth and operational helpers
    otp = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    subject = Column(String(200), nullable=True)

    # Synonyms for backwards compatibility
    last_login = synonym("lastlogin")
    phone = synonym("phonenumber")
    activation_status = synonym("activation")

    # Relationships (Student is decoupled; only Admin and Teacher remain here)
    school = relationship("School", foreign_keys=[school_id], back_populates="teachers_legacy")
    administered_schools = relationship(
        "School",
        foreign_keys="School.school_admin_id",
        back_populates="school_admin"
    )
    teacher = relationship(
        "Teacher",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        first = kwargs.pop("first_Name", None) or kwargs.pop("first_name", None)
        last = kwargs.pop("last_Name", None) or kwargs.pop("last_name", None)
        if "name" not in kwargs:
            full = []
            if first:
                full.append(str(first).strip())
            if last:
                full.append(str(last).strip())
            kwargs["name"] = " ".join(full).strip()

        if "phone" in kwargs and "phonenumber" not in kwargs:
            kwargs["phonenumber"] = kwargs.pop("phone")

        if "last_login" in kwargs and "lastlogin" not in kwargs:
            kwargs["lastlogin"] = kwargs.pop("last_login")

        if "activation_status" in kwargs and "activation" not in kwargs:
            act_val = kwargs.pop("activation_status")
            if hasattr(act_val, "value"):
                kwargs["activation"] = StatusEnum(act_val.value)
            elif isinstance(act_val, str):
                kwargs["activation"] = StatusEnum(act_val)
            else:
                kwargs["activation"] = act_val

        if "role" in kwargs and hasattr(kwargs["role"], "value"):
            kwargs["role"] = kwargs["role"].value

        super().__init__(**kwargs)

    @property
    def first_Name(self) -> str:
        if not self.name:
            return ""
        parts = self.name.split(" ", 1)
        return parts[0]

    @first_Name.setter
    def first_Name(self, val: str):
        last = self.last_Name or ""
        self.name = f"{str(val).strip()} {last}".strip()

    @property
    def last_Name(self) -> str:
        if not self.name:
            return ""
        parts = self.name.split(" ", 1)
        return parts[1] if len(parts) > 1 else ""

    @last_Name.setter
    def last_Name(self, val: str):
        first = self.first_Name or ""
        self.name = f"{first} {str(val).strip()}".strip()

    @property
    def schools(self):
        return [self.school] if self.school else []
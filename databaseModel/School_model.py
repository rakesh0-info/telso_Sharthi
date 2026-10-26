from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship, synonym
from database_config import Base
from enums.dbEnums import StatusEnum


class School(Base):
    __tablename__ = "school"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    school_code = Column(String(50), nullable=False, unique=True)
    total_student = Column(Integer, default=0, nullable=False)
    total_teacher = Column(Integer, default=0, nullable=False)
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
    distc = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    school_admin_id = Column(Integer, ForeignKey("User.id", ondelete="SET NULL"), nullable=True)
    school_ph_no = Column(String(20), nullable=True)
    address = Column(String(200), nullable=True)

    # Synonyms for backwards compatibility
    school_name = synonym("name")
    School_Code = synonym("school_code")
    District = synonym("distc")
    Region = synonym("region")
    admin_id = synonym("school_admin_id")
    phone = synonym("school_ph_no")
    activation_status = synonym("activation")

    # Relationships
    school_admin = relationship(
        "User",
        foreign_keys=[school_admin_id],
        back_populates="administered_schools"
    )
    teachers_legacy = relationship(
        "User",
        foreign_keys="User.school_id",
        back_populates="school"
    )
    teachers = relationship(
        "Teacher",
        back_populates="school",
        cascade="all, delete-orphan"
    )
    classes = relationship(
        "ClassModel",
        back_populates="school",
        cascade="all, delete-orphan"
    )
    students = relationship(
        "Student",
        back_populates="school",
        cascade="all, delete-orphan"
    )
    labs = relationship(
        "Lab",
        back_populates="school",
        cascade="all, delete-orphan"
    )
    schedulers = relationship(
        "ClassScheduler",
        back_populates="school",
        cascade="all, delete-orphan"
    )
    subjects = relationship(
        "Subject",
        back_populates="school",
        cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        # Backward compatibility for parameter aliases
        if "school_name" in kwargs and "name" not in kwargs:
            kwargs["name"] = kwargs.pop("school_name")
        if "School_Code" in kwargs and "school_code" not in kwargs:
            kwargs["school_code"] = kwargs.pop("School_Code")
        if "District" in kwargs and "distc" not in kwargs:
            kwargs["distc"] = kwargs.pop("District")
        if "district" in kwargs and "distc" not in kwargs:
            kwargs["distc"] = kwargs.pop("district")
        if "Region" in kwargs and "region" not in kwargs:
            kwargs["region"] = kwargs.pop("Region")
        if "admin_id" in kwargs and "school_admin_id" not in kwargs:
            kwargs["school_admin_id"] = kwargs.pop("admin_id")
        if "phone" in kwargs and "school_ph_no" not in kwargs:
            kwargs["school_ph_no"] = kwargs.pop("phone")
        if "activation_status" in kwargs and "activation" not in kwargs:
            act_val = kwargs.pop("activation_status")
            if hasattr(act_val, "value"):
                kwargs["activation"] = StatusEnum(act_val.value)
            elif isinstance(act_val, str):
                kwargs["activation"] = StatusEnum(act_val)
            else:
                kwargs["activation"] = act_val

        super().__init__(**kwargs)
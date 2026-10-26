from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship, synonym
from database_config import Base
from enums.dbEnums import StatusEnum


class Lab(Base):
    __tablename__ = "lab"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("school.id", ondelete="CASCADE"), nullable=False)
    lab_name = Column(String(150), nullable=False)
    lab_assistant_id = Column(Integer, ForeignKey("User.id", ondelete="SET NULL"), nullable=True)
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
    lab_time = Column(DateTime, nullable=True)

    # Synonyms
    activation_status = synonym("activation")

    # Relationships
    school = relationship("School", back_populates="labs")
    lab_assistant = relationship("User")

    def __init__(self, **kwargs):
        if "activation_status" in kwargs and "activation" not in kwargs:
            kwargs["activation"] = kwargs.pop("activation_status")
        super().__init__(**kwargs)


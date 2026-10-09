from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Enum, DateTime
from sqlalchemy.orm import relationship
from database_config import Base
from enums.roleEnum import Role
from enums.userActivationEnum import activation

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    first_Name = Column(String, nullable=False)
    last_Name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
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

    schools = relationship("School", back_populates="school_admin")
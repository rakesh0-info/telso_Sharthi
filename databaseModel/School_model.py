from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database_config import Base
from enums.roleEnum import Role
from enums.userActivationEnum import activation

class School(Base):
    __tablename__ = "school"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_name = Column(String(200), nullable=False)
    School_Code = Column(String(10), nullable=False,unique=True)
    District = Column(String(200), nullable=False)
    Region = Column(String(200), nullable=False)
    address = Column(String(200))
    phone = Column(String(12))
    
 
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
  
    school_admin = relationship("User", back_populates="schools")

    activation_status = Column(
        Enum(activation, name="activation_Status", schema="telso_sharthi", inherit_schema=True),
        default=activation.ACTIVE,
    )
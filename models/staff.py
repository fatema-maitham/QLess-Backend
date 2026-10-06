# models/staff.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class StaffModel(BaseModel):
    __tablename__ = "staff"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    position = Column(String)
    counter_number = Column(Integer, default=1, server_default="1", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("UserModel", back_populates="staff_assignments")
    business = relationship("BusinessModel", back_populates="staff")
    branch = relationship("BranchModel", back_populates="staff")

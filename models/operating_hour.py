# models/operating_hour.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Time
from sqlalchemy.orm import relationship
from .base import BaseModel


class OperatingHourModel(BaseModel):
    __tablename__ = "operating_hours"

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(String, nullable=False)  # monday ... sunday
    open_time = Column(Time, nullable=True)
    close_time = Column(Time, nullable=True)
    is_closed = Column(Boolean, default=False, nullable=False)

    business = relationship("BusinessModel", back_populates="operating_hours")
    branch = relationship("BranchModel", back_populates="operating_hours")

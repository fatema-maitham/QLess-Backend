# models/branch.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class BranchModel(BaseModel):
    __tablename__ = "branches"

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    email = Column(String)
    image = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)

    business = relationship("BusinessModel", back_populates="branches")
    services = relationship("ServiceModel", back_populates="branch", cascade="all, delete-orphan")
    operating_hours = relationship("OperatingHourModel", back_populates="branch", cascade="all, delete-orphan")
    staff = relationship("StaffModel", back_populates="branch", cascade="all, delete-orphan")
    announcements = relationship("AnnouncementModel", back_populates="branch")
    queues = relationship("QueueModel", back_populates="branch", cascade="all, delete-orphan")
    bookings = relationship("BookingModel", back_populates="branch", cascade="all, delete-orphan")

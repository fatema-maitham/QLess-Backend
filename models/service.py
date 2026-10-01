# models/service.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class ServiceModel(BaseModel):
    __tablename__ = "services"

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    duration_minutes = Column(Integer)
    is_active = Column(Boolean, default=True, nullable=False)

    business = relationship("BusinessModel", back_populates="services")
    branch = relationship("BranchModel", back_populates="services")
    queues = relationship("QueueModel", back_populates="service")
    bookings = relationship("BookingModel", back_populates="service", cascade="all, delete-orphan")

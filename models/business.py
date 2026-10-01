# models/business.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class BusinessModel(BaseModel):
    __tablename__ = "businesses"

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(String)
    phone = Column(String)
    email = Column(String)
    image = Column(String)
    approval_status = Column(String, default="draft", nullable=False)  # draft, pending, approved, rejected
    rejection_reason = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    owner = relationship("UserModel", back_populates="businesses")
    category = relationship("CategoryModel", back_populates="businesses")
    branches = relationship("BranchModel", back_populates="business", cascade="all, delete-orphan")
    services = relationship("ServiceModel", back_populates="business", cascade="all, delete-orphan")
    operating_hours = relationship("OperatingHourModel", back_populates="business", cascade="all, delete-orphan")
    staff = relationship("StaffModel", back_populates="business", cascade="all, delete-orphan")
    announcements = relationship("AnnouncementModel", back_populates="business", cascade="all, delete-orphan")
    queues = relationship("QueueModel", back_populates="business", cascade="all, delete-orphan")
    bookings = relationship("BookingModel", back_populates="business", cascade="all, delete-orphan")
    reviews = relationship("ReviewModel", back_populates="business", cascade="all, delete-orphan")
    favorites = relationship("FavoriteModel", back_populates="business", cascade="all, delete-orphan")

# models/business.py
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


def utc_now() -> datetime:
    """Now in UTC, without timezone info (same style as the other DateTime columns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    payments = relationship("PaymentModel", back_populates="business", cascade="all, delete-orphan")

    # ---------- subscription helpers (not saved in the database) ----------

    def _paid_payments(self):
        return [p for p in self.payments if p.status == "paid" and p.period_end is not None]

    @property
    def paid_until(self):
        """The date the owner's plan runs out, or None if they never paid."""
        paid = self._paid_payments()
        return max(p.period_end for p in paid) if paid else None

    @property
    def is_paid(self) -> bool:
        """True while the owner has a plan that hasn't run out yet."""
        until = self.paid_until
        return until is not None and until > utc_now()

    @property
    def current_plan(self):
        """monthly / yearly from the latest paid payment, or None."""
        paid = self._paid_payments()
        if not paid:
            return None
        return max(paid, key=lambda p: p.period_end).plan
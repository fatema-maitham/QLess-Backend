# models/booking.py

from sqlalchemy import Column, Date, ForeignKey, Integer, String, Time
from sqlalchemy.orm import relationship

from .base import BaseModel


class BookingModel(BaseModel):
    __tablename__ = "bookings"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    business_id = Column(
        Integer,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
    )

    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
    )

    service_id = Column(
        Integer,
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )

    booking_date = Column(Date, nullable=False)
    booking_time = Column(Time, nullable=False)

    # A valid booking is confirmed immediately.
    #
    # confirmed -> completed
    # confirmed -> cancelled
    # confirmed -> no_show
    status = Column(
        String,
        default="confirmed",
        nullable=False,
    )

    user = relationship(
        "UserModel",
        back_populates="bookings",
    )

    business = relationship(
        "BusinessModel",
        back_populates="bookings",
    )

    branch = relationship(
        "BranchModel",
        back_populates="bookings",
    )

    service = relationship(
        "ServiceModel",
        back_populates="bookings",
    )
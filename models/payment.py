# models/payment.py
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class PaymentModel(BaseModel):
    """One subscription payment made by a business owner.

    We never save the full card number or the CVC. Only the brand and last 4 digits.
    """

    __tablename__ = "payments"

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    plan = Column(String, nullable=False)  # monthly, yearly
    amount = Column(Numeric(10, 3), nullable=False)  # BHD has 3 decimals
    currency = Column(String, default="BHD", nullable=False)
    status = Column(String, default="paid", nullable=False)  # paid, failed
    failure_reason = Column(String, nullable=True)

    card_brand = Column(String, nullable=True)  # visa, mastercard, amex
    card_last4 = Column(String(4), nullable=True)
    card_holder = Column(String, nullable=True)
    reference = Column(String, unique=True, nullable=False, index=True)  # e.g. QL-8F2A91C3

    # The time this payment covers (only for paid payments)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)

    business = relationship("BusinessModel", back_populates="payments")
    owner = relationship("UserModel")
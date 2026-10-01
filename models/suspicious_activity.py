# models/suspicious_activity.py
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class SuspiciousActivityModel(BaseModel):
    __tablename__ = "suspicious_activities"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    queue_id = Column(Integer, ForeignKey("queues.id", ondelete="SET NULL"), nullable=True)
    activity_type = Column(String, nullable=False)  # e.g. repeated_no_show
    description = Column(String)
    severity = Column(String, default="low", nullable=False)  # low, medium, high
    status = Column(String, default="open", nullable=False)  # open, reviewed, dismissed
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Two links to users, so each relationship says which column it uses
    user = relationship("UserModel", foreign_keys=[user_id])
    reviewer = relationship("UserModel", foreign_keys=[reviewed_by])
    queue = relationship("QueueModel", back_populates="suspicious_activities")

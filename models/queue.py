# models/queue.py
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class QueueModel(BaseModel):
    __tablename__ = "queues"

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    status = Column(String, default="closed", nullable=False)  # open, paused, closed
    current_number = Column(Integer, default=0, nullable=False)
    max_capacity = Column(Integer, nullable=True)
    average_service_minutes = Column(Integer, default=10, nullable=False)
    no_show_grace_minutes = Column(Integer, default=5, nullable=False)

    business = relationship("BusinessModel", back_populates="queues")
    branch = relationship("BranchModel", back_populates="queues")
    service = relationship("ServiceModel", back_populates="queues")
    entries = relationship("QueueEntryModel", back_populates="queue", cascade="all, delete-orphan")
    suspicious_activities = relationship("SuspiciousActivityModel", back_populates="queue")

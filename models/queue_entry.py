# models/queue_entry.py
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from .base import BaseModel


class QueueEntryModel(BaseModel):
    __tablename__ = "queue_entries"
    __table_args__ = (UniqueConstraint("queue_id", "queue_number", name="uq_queue_entry_number"),)

    queue_id = Column(Integer, ForeignKey("queues.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    queue_number = Column(Integer, nullable=False)
    status = Column(String, default="waiting", nullable=False)  # waiting, called, checked_in, completed, cancelled, no_show
    on_the_way = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime, default=func.now())
    called_at = Column(DateTime, nullable=True)
    checked_in_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    no_show_at = Column(DateTime, nullable=True)
    counter_number = Column(Integer, nullable=True)  # which desk called this ticket

    queue = relationship("QueueModel", back_populates="entries")
    user = relationship("UserModel", back_populates="queue_entries")
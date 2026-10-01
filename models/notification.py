# models/notification.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class NotificationModel(BaseModel):
    __tablename__ = "notifications"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # e.g. called, turn_approaching, no_show, booking, business_status
    title = Column(String, nullable=False)
    message = Column(String)
    is_read = Column(Boolean, default=False, nullable=False)

    user = relationship("UserModel", back_populates="notifications")

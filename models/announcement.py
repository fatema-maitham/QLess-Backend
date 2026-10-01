# models/announcement.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class AnnouncementModel(BaseModel):
    __tablename__ = "business_announcements"

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)  # optional
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    business = relationship("BusinessModel", back_populates="announcements")
    branch = relationship("BranchModel", back_populates="announcements")

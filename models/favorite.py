# models/favorite.py
from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import BaseModel


class FavoriteModel(BaseModel):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "business_id", name="uq_favorite_user_business"),)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)

    user = relationship("UserModel", back_populates="favorites")
    business = relationship("BusinessModel", back_populates="favorites")

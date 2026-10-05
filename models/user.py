# models/user.py
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from config.environment import JWT_SECRET
from .base import BaseModel

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserModel(BaseModel):
    __tablename__ = "users"

    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    phone = Column(String)
    profile_image = Column(String)
    cover_image = Column(String)
    no_show_count = Column(Integer, default=0, nullable=False)
    restricted_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    role = relationship("RoleModel", back_populates="users")
    businesses = relationship("BusinessModel", back_populates="owner", cascade="all, delete-orphan")
    staff_assignments = relationship("StaffModel", back_populates="user", cascade="all, delete-orphan")
    queue_entries = relationship("QueueEntryModel", back_populates="user", cascade="all, delete-orphan")
    bookings = relationship("BookingModel", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("NotificationModel", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("ReviewModel", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("FavoriteModel", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, plain_txt_password: str):
        self.password_hash = pwd_context.hash(plain_txt_password)

    def verify_password(self, plain_txt_password: str) -> bool:
        return pwd_context.verify(plain_txt_password, self.password_hash)

    def generate_token(self):
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(days=1),  # Expires in 1 day
            "iat": datetime.now(timezone.utc),  # Issued at
            "sub": str(self.id),  # The user ID
        }
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

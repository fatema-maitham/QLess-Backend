# models/role.py
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class RoleModel(BaseModel):
    __tablename__ = "roles"

    name = Column(String, unique=True, nullable=False)  # customer, owner, staff, admin
    description = Column(String)

    users = relationship("UserModel", back_populates="role")

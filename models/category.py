# models/category.py
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from .base import BaseModel


class CategoryModel(BaseModel):
    __tablename__ = "categories"

    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    image = Column(String)

    businesses = relationship("BusinessModel", back_populates="category")

# serializers/category.py
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CategorySchema(BaseModel):
    """What the API sends back about a category."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    image: Optional[str] = None


class CategoryCreateSchema(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    image: Optional[str] = None


class CategoryUpdateSchema(BaseModel):
    # Every field is optional so the admin can change just one thing
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    image: Optional[str] = None
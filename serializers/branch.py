# serializers/branch.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BranchCreateSchema(BaseModel):
    name: str = Field(min_length=1)
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    image: Optional[str] = None


class BranchUpdateSchema(BaseModel):
    """All optional. Only send what you want to change."""

    name: Optional[str] = Field(default=None, min_length=1)
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    image: Optional[str] = None


class BranchSchema(BaseModel):
    """What the API sends back about a branch."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    image: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
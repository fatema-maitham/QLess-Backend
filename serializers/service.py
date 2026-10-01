from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreateSchema(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)  # e.g. 15


class ServiceUpdateSchema(BaseModel):
    """All optional. Only send what you want to change."""

    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)


class ServiceSchema(BaseModel):
    """What the API sends back about a service."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    branch_id: int
    name: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
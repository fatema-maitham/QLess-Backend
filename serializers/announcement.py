from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AnnouncementCreateSchema(BaseModel):
    title: str = Field(min_length=1)
    message: str = Field(min_length=1)
    branch_id: Optional[int] = None  # leave empty for the whole business


class AnnouncementUpdateSchema(BaseModel):
    """All optional. Only send what you want to change."""

    title: Optional[str] = Field(default=None, min_length=1)
    message: Optional[str] = Field(default=None, min_length=1)
    branch_id: Optional[int] = None
    is_active: Optional[bool] = None


class AnnouncementSchema(BaseModel):
    """What the API sends back about an announcement."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    branch_id: Optional[int] = None
    title: str
    message: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
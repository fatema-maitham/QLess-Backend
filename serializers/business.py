from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BusinessCategorySchema(BaseModel):
    """Small version of a category, shown inside a business."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class BusinessCreateSchema(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    image: Optional[str] = None
    category_id: int



class BusinessUpdateSchema(BaseModel):
    """All optional. Send approval_status "pending" to submit or resubmit for approval."""

    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    image: Optional[str] = None
    category_id: Optional[int] = None
    # Owners can only move a business to "pending". Approve/reject is the admin's job.
    approval_status: Optional[Literal["pending"]] = None
    is_active: Optional[bool] = None


class BusinessSchema(BaseModel):
    """What the API sends back about a business."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    category_id: Optional[int] = None
    category: Optional[BusinessCategorySchema] = None
    name: str
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    image: Optional[str] = None
    approval_status: str
    rejection_reason: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
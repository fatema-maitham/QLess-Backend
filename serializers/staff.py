# serializers/staff.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StaffCreateSchema(BaseModel):
    user_email: str = Field(min_length=3)  # the person must already have an account
    position: Optional[str] = None  # e.g. "Cashier", "Receptionist"

    @field_validator("user_email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return value.strip().lower()


class StaffUpdateSchema(BaseModel):
    """All optional. Only send what you want to change."""

    position: Optional[str] = None
    is_active: Optional[bool] = None


class StaffUserSchema(BaseModel):
    """The staff member's basic account info."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None


class StaffSchema(BaseModel):
    """What the owner sees about a staff member."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    business_id: int
    branch_id: int
    position: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    user: StaffUserSchema


# ----- for GET /staff/me (the staff member's own home page) -----

class StaffBusinessSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class StaffBranchSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None


class StaffQueueSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str


class StaffMeSchema(BaseModel):
    id: int
    position: Optional[str] = None
    business: StaffBusinessSchema
    branch: StaffBranchSchema
    queues: List[StaffQueueSchema]
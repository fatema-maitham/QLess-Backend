from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class UserSchema(BaseModel):
    """What the API sends back about a user. Never includes the password."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    role: str
    no_show_count: int
    restricted_until: Optional[datetime] = None
    is_active: bool
    created_at: Optional[datetime] = None

    # The model gives us a RoleModel; send just its name ("customer", "owner", ...)
    @field_validator("role", mode="before")
    @classmethod
    def role_to_name(cls, value):
        return value.name if hasattr(value, "name") else value
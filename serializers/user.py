from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserSchema(BaseModel):
    """What the API sends back about a user. Never includes the password."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    cover_image: Optional[str] = None
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


class UserUpdateSchema(BaseModel):
    """Fields a user can change on their own profile. All optional."""

    name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[str] = Field(default=None, min_length=3)
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    cover_image: Optional[str] = None
    # To change the password, send both of these
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(default=None, min_length=6)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        if value is None:
            return value
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Enter a valid email")
        return value
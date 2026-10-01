from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from serializers.user import UserSchema


class SignUpSchema(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)
    phone: Optional[str] = None
    # People can only sign themselves up as a customer or a business owner.
    # Staff are added by an owner, and admins are created in seed.py.
    role: Literal["customer", "owner"] = "customer"

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Enter a valid email")
        return value


class SignInSchema(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthResponseSchema(BaseModel):
    token: str
    user: UserSchema
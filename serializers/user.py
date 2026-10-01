# serializers/user.py

from pydantic import BaseModel

# Form Validations
class UserRegistrationSchema(BaseModel):
    username: str  # User's unique name
    email: str  # User's email address
    password: str  # Plain text password for user registration (will be hashed before saving)

class UserLoginSchema(BaseModel):
    username: str  # User's unique name
    password: str  # Plain text password for user registration (will be hashed before saving)

# Response Schemas
class UserSchema(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        orm_mode = True

class UserTokenSchema(BaseModel):
    token: str
    message: str

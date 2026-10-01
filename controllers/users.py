# controllers/users.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.user import UserModel
from serializers.user import UserSchema, UserRegistrationSchema, UserLoginSchema, UserTokenSchema
from database import get_db
from dependencies.get_current_user import get_current_user

router = APIRouter()

@router.post("/register", response_model=UserTokenSchema, status_code=201)
def create_user(user: UserRegistrationSchema, db: Session = Depends(get_db)):
    # Check if the username or email already exists
    existing_user = db.query(UserModel).filter(
        (UserModel.username == user.username) | (UserModel.email == user.email)
    ).first()

    if existing_user:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    # Initialize the user class (instance)
    new_user = UserModel(username=user.username, email=user.email)
    # Use the set_password method to hash the password
    new_user.set_password(user.password)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT token
    token = new_user.generate_token()

        # Return token and a success message
    return {"token": token, "message": "Login successful"}

@router.post("/login", response_model=UserTokenSchema, status_code=201)
def login(user: UserLoginSchema, db: Session = Depends(get_db)):

    # Find the user by username
    db_user = db.query(UserModel).filter(UserModel.username == user.username).first()

    # Check if the user exists and if the password is correct
    if not db_user or not db_user.verify_password(user.password):
        raise HTTPException(status_code=409, detail="Invalid username or password")

    # Generate JWT token
    token = db_user.generate_token()

    # Return token and a success message
    return {"token": token, "message": "Login successful"}

@router.get('/current_user', response_model=UserSchema)
def current_user(user: UserSchema = Depends(get_current_user)):
    return user

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.role import RoleModel
from models.user import UserModel
from serializers.auth import AuthResponseSchema, SignInSchema, SignUpSchema

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/sign-up", response_model=AuthResponseSchema, status_code=status.HTTP_201_CREATED)
def sign_up(data: SignUpSchema, db: Session = Depends(get_db)):
    if db.query(UserModel).filter(UserModel.email == data.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    role = db.query(RoleModel).filter(RoleModel.name == data.role).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Roles are missing. Run seed.py")

    user = UserModel(name=data.name.strip(), email=data.email, phone=data.phone, role=role)
    user.set_password(data.password)

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"token": user.generate_token(), "user": user}


@router.post("/sign-in", response_model=AuthResponseSchema)
def sign_in(data: SignInSchema, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == data.email).first()

    # Same message for wrong email and wrong password, so nobody can guess emails
    if not user or not user.verify_password(data.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")

    return {"token": user.generate_token(), "user": user}
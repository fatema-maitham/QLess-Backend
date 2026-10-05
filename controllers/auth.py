from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.environment import FRONTEND_URL, JWT_SECRET, SMTP_HOST, SMTP_PASSWORD, SMTP_USER
from database import get_db
from models.role import RoleModel
from models.user import UserModel
from serializers.auth import (
    AuthResponseSchema, ForgotPasswordSchema, ResetPasswordSchema, SignInSchema, SignUpSchema,
)
from services.email import send_email

router = APIRouter(prefix="/auth", tags=["Auth"])

# Reset links use their own secret, so a reset link can never be used to sign in
RESET_SECRET = f"{JWT_SECRET}-reset"
RESET_MINUTES = 30


def make_reset_token(user: UserModel) -> str:
    payload = {
        "sub": str(user.id),
        # Part of the current password hash: once the password changes, the link stops working
        "pw": user.password_hash[-12:],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=RESET_MINUTES),
    }
    return jwt.encode(payload, RESET_SECRET, algorithm="HS256")


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



@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordSchema, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == data.email).first()

  

    response = {"message": "We sent a reset link to your email."}
    link = None
    if user and user.is_active:
        link = f"{FRONTEND_URL}/reset-password?token={make_reset_token(user)}"
        send_email(
            to=user.email,
            subject="Reset your QLess password",
            body=(
                f"Hi {user.name},\n\n"
                "We got a request to reset the password for your QLess account.\n\n"
                f"Click the link below to choose a new password:\n{link}\n\n"
                f"This link works for {RESET_MINUTES} minutes and can only be used once.\n\n"
                "If you didn't ask for this, you can ignore this email. Your password won't change.\n\n"
                "— The QLess team"
            ),
        )

    # No email set up (fake accounts while developing): give the link to the page instead
    if link and not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        response["reset_link"] = link
    return response


@router.post("/reset-password")
def reset_password(data: ResetPasswordSchema, db: Session = Depends(get_db)):
    expired = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This link has expired or was already used. Please ask for a new one.",
    )
    try:
        payload = jwt.decode(data.token, RESET_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise expired

    user = db.query(UserModel).filter(UserModel.id == int(payload["sub"])).first()
    if not user or not user.is_active or user.password_hash[-12:] != payload.get("pw"):
        raise expired

    user.set_password(data.new_password)
    db.commit()
    return {"message": "Your password was changed."}
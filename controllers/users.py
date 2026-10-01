from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies.get_current_user import get_current_user
from models.user import UserModel
from serializers.user import UserSchema, UserUpdateSchema

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserSchema)
def get_me(current_user: UserModel = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserSchema)
def update_me(
    data: UserUpdateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    changes = data.model_dump(exclude_unset=True)

    # Email must stay unique
    new_email = changes.get("email")
    if new_email and new_email != current_user.email:
        taken = db.query(UserModel).filter(UserModel.email == new_email).first()
        if taken:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    # Password change needs the current password
    current_password = changes.pop("current_password", None)
    new_password = changes.pop("new_password", None)
    if new_password:
        if not current_password or not current_user.verify_password(current_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        current_user.set_password(new_password)

    # Update the normal fields (name, email, phone, profile_image)
    for field, value in changes.items():
        if field == "name" and value:
            value = value.strip()
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me")
def delete_me(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted"}
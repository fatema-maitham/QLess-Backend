# controllers/favorites.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies.roles import require_customer
from models.business import BusinessModel
from models.favorite import FavoriteModel
from models.user import UserModel
from serializers.favorite import FavoriteCreateSchema, FavoriteSchema

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.get("", response_model=list[FavoriteSchema])
def get_favorites(
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    return (
        db.query(FavoriteModel)
        .filter(FavoriteModel.user_id == user.id)
        .order_by(FavoriteModel.created_at.desc())
        .all()
    )


@router.post("", response_model=FavoriteSchema, status_code=status.HTTP_201_CREATED)
def create_favorite(
    data: FavoriteCreateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    business = db.query(BusinessModel).filter(BusinessModel.id == data.business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    if business.approval_status != "approved" or not business.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This business can't be favorited")

    already = (
        db.query(FavoriteModel)
        .filter(FavoriteModel.user_id == user.id, FavoriteModel.business_id == business.id)
        .first()
    )
    if already:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in your favorites")

    favorite = FavoriteModel(user_id=user.id, business_id=business.id)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@router.delete("/{business_id}")
def delete_favorite(
    business_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    favorite = (
        db.query(FavoriteModel)
        .filter(FavoriteModel.user_id == user.id, FavoriteModel.business_id == business_id)
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in your favorites")

    db.delete(favorite)
    db.commit()
    return {"message": "Removed from favorites"}
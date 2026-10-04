from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies.get_optional_user import get_optional_user
from dependencies.roles import require_owner
from models.business import BusinessModel
from models.category import CategoryModel
from models.user import UserModel
from serializers.business import BusinessCreateSchema, BusinessSchema, BusinessUpdateSchema
from services.audit_log import paused_by_admin

# No prefix here because this file also has /users/me/businesses.
# The public list GET /businesses is in Fatema's controllers/browse.py.
router = APIRouter(tags=["Businesses"])


# ---------- helpers ----------

def get_owned_business(business_id: int, db: Session, user: UserModel) -> BusinessModel:
    """Find a business and make sure the logged-in owner owns it."""
    business = db.query(BusinessModel).filter(BusinessModel.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    if business.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your business")
    return business


def check_category(category_id: Optional[int], db: Session):
    if category_id is None:
        return
    if not db.query(CategoryModel).filter(CategoryModel.id == category_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


# ---------- routes ----------

@router.post("/businesses", response_model=BusinessSchema, status_code=status.HTTP_201_CREATED)
def create_business(
    data: BusinessCreateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    check_category(data.category_id, db)

    business = BusinessModel(**data.model_dump(), owner_id=current_user.id, approval_status="draft")
    business.name = business.name.strip()

    db.add(business)
    db.commit()
    db.refresh(business)
    return business


@router.get("/users/me/businesses", response_model=List[BusinessSchema])
def get_my_businesses(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """The owner's own businesses, every status (draft, pending, approved, rejected)."""
    return (
        db.query(BusinessModel)
        .filter(BusinessModel.owner_id == current_user.id)
        .order_by(BusinessModel.created_at.desc())
        .all()
    )


@router.get("/businesses/{business_id}", response_model=BusinessSchema)
def show_business(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
):
    business = db.query(BusinessModel).filter(BusinessModel.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    is_public = business.approval_status == "approved" and business.is_active
    can_see_private = current_user is not None and (
        current_user.id == business.owner_id or current_user.role.name == "admin"
    )

    # Drafts, pending, rejected and deactivated businesses are hidden from the public
    if not is_public and not can_see_private:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    return business


@router.patch("/businesses/{business_id}", response_model=BusinessSchema)
def update_business(
    business_id: int,
    data: BusinessUpdateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    business = get_owned_business(business_id, db, current_user)
    changes = data.model_dump(exclude_unset=True)

    if "category_id" in changes:
        check_category(changes["category_id"], db)

    # Submit / resubmit for admin approval
    new_status = changes.pop("approval_status", None)
    if new_status == "pending":
        if business.approval_status not in ("draft", "rejected"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only draft or rejected businesses can be submitted (current status: {business.approval_status})",
            )
        business.approval_status = "pending"
        business.rejection_reason = None

    # Owner turns their business on/off. They can't undo an admin's suspension.
    new_active = changes.pop("is_active", None)
    if new_active is not None and new_active != business.is_active:
        if new_active and paused_by_admin(db, "business", business.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An admin suspended this business. Contact QLess support to turn it back on.",
            )
        business.is_active = new_active

    for field, value in changes.items():
        if field == "name":
            if value is None:
                continue  # name can't be empty
            value = value.strip()
        setattr(business, field, value)

    db.commit()
    db.refresh(business)
    return business


@router.delete("/businesses/{business_id}")
def delete_business(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """Deactivate (not a real delete), so bookings, reviews and history stay safe."""
    business = get_owned_business(business_id, db, current_user)
    business.is_active = False
    db.commit()
    return {"message": "Business deactivated"}
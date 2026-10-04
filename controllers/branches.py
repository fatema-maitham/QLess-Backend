from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from controllers.businesses import get_owned_business
from database import get_db
from dependencies.get_optional_user import get_optional_user
from dependencies.roles import require_owner
from models.branch import BranchModel
from models.business import BusinessModel
from models.user import UserModel
from serializers.branch import BranchCreateSchema, BranchSchema, BranchUpdateSchema
from services.opening_hours import branch_is_open_now
from services.audit_log import paused_by_admin

router = APIRouter(tags=["Branches"])


# ---------- helpers ----------

def can_manage(user: Optional[UserModel], business: BusinessModel) -> bool:
    """True if this user is the business owner or an admin."""
    return user is not None and (user.id == business.owner_id or user.role.name == "admin")


def is_public_business(business: BusinessModel) -> bool:
    return business.approval_status == "approved" and business.is_active


def get_owned_branch(branch_id: int, db: Session, user: UserModel) -> BranchModel:
    """Find a branch and make sure the logged-in owner owns its business."""
    branch = db.query(BranchModel).filter(BranchModel.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    if branch.business.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your branch")
    return branch


# ---------- routes ----------

@router.get("/businesses/{business_id}/branches", response_model=List[BranchSchema])
def get_branches(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
):
    business = db.query(BusinessModel).filter(BusinessModel.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    manager = can_manage(current_user, business)

    # The public only sees branches of approved, active businesses
    if not manager and not is_public_business(business):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    query = db.query(BranchModel).filter(BranchModel.business_id == business_id)

    # The owner and admin also see deactivated branches; the public doesn't
    if not manager:
        query = query.filter(BranchModel.is_active.is_(True))

    branches = query.order_by(BranchModel.name).all()
    for branch in branches:
        branch.is_open_now = branch_is_open_now(branch)
    return branches

@router.post(
    "/businesses/{business_id}/branches",
    response_model=BranchSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_branch(
    business_id: int,
    data: BranchCreateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    business = get_owned_business(business_id, db, current_user)

    branch = BranchModel(**data.model_dump(), business_id=business.id)
    branch.name = branch.name.strip()

    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch


@router.get("/branches/{branch_id}", response_model=BranchSchema)
def show_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
):
    branch = db.query(BranchModel).filter(BranchModel.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    is_public = branch.is_active and is_public_business(branch.business)

    if not is_public and not can_manage(current_user, branch.business):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    branch.is_open_now = branch_is_open_now(branch)
    return branch

@router.patch("/branches/{branch_id}", response_model=BranchSchema)
def update_branch(
    branch_id: int,
    data: BranchUpdateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    branch = get_owned_branch(branch_id, db, current_user)
    changes = data.model_dump(exclude_unset=True)

    # Owner turns their branch on/off. They can't undo an admin's pause.
    new_active = changes.pop("is_active", None)
    if new_active is not None and new_active != branch.is_active:
        if new_active and paused_by_admin(db, "branch", branch.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An admin paused this branch. Contact QLess support to turn it back on.",
            )
        branch.is_active = new_active

    for field, value in changes.items():
        if field == "name":
            if value is None:
                continue  # name can't be empty
            value = value.strip()
        setattr(branch, field, value)

    db.commit()
    db.refresh(branch)
    branch.is_open_now = branch_is_open_now(branch)
    return branch

@router.delete("/branches/{branch_id}")
def delete_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """Deactivate (not a real delete), so queues, bookings and history stay safe."""
    branch = get_owned_branch(branch_id, db, current_user)
    branch.is_active = False
    db.commit()
    return {"message": "Branch deactivated"}
# controllers/hours.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from controllers.branches import can_manage, get_owned_branch, is_public_business
from database import get_db
from dependencies.get_optional_user import get_optional_user
from dependencies.roles import require_owner
from models.branch import BranchModel
from models.operating_hour import OperatingHourModel
from models.user import UserModel
from serializers.operating_hour import (
    OperatingHourCreateSchema,
    OperatingHourSchema,
    OperatingHourUpdateSchema,
)
from services.opening_hours import day_index

router = APIRouter(tags=["Operating Hours"])


# ---------- helpers ----------

def get_owned_hour(hour_id: int, db: Session, user: UserModel) -> OperatingHourModel:
    """Find an operating hour and make sure the logged-in owner owns its business."""
    hour = db.query(OperatingHourModel).filter(OperatingHourModel.id == hour_id).first()
    if not hour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operating hour not found")
    if hour.business.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your branch")
    return hour


def check_day_is_free(db: Session, branch_id: int, day: str, ignore_id: Optional[int] = None):
    """Each branch can only have one row per day."""
    query = db.query(OperatingHourModel).filter(
        OperatingHourModel.branch_id == branch_id,
        OperatingHourModel.day_of_week == day,
    )
    if ignore_id is not None:
        query = query.filter(OperatingHourModel.id != ignore_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hours for {day} already exist for this branch. Edit them instead.",
        )


# ---------- routes ----------

@router.get("/branches/{branch_id}/hours", response_model=List[OperatingHourSchema])
def get_operating_hours(
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

    hours = db.query(OperatingHourModel).filter(OperatingHourModel.branch_id == branch_id).all()
    return sorted(hours, key=lambda h: day_index(h.day_of_week))  # Monday first


@router.post(
    "/branches/{branch_id}/hours",
    response_model=OperatingHourSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_operating_hour(
    branch_id: int,
    data: OperatingHourCreateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    branch = get_owned_branch(branch_id, db, current_user)
    check_day_is_free(db, branch.id, data.day_of_week)

    hour = OperatingHourModel(**data.model_dump(), branch_id=branch.id, business_id=branch.business_id)

    # A closed day doesn't need times
    if hour.is_closed:
        hour.open_time = None
        hour.close_time = None

    db.add(hour)
    db.commit()
    db.refresh(hour)
    return hour


@router.patch("/hours/{hour_id}", response_model=OperatingHourSchema)
def update_operating_hour(
    hour_id: int,
    data: OperatingHourUpdateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    hour = get_owned_hour(hour_id, db, current_user)
    changes = data.model_dump(exclude_unset=True)

    if changes.get("day_of_week") and changes["day_of_week"] != hour.day_of_week:
        check_day_is_free(db, hour.branch_id, changes["day_of_week"], ignore_id=hour.id)

    for field, value in changes.items():
        if field in ("day_of_week", "is_closed") and value is None:
            continue
        setattr(hour, field, value)

    # Check the final result still makes sense
    if hour.is_closed:
        hour.open_time = None
        hour.close_time = None
    else:
        if hour.open_time is None or hour.close_time is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="open_time and close_time are required unless is_closed is true",
            )
        if hour.open_time == hour.close_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="open_time and close_time can't be the same",
            )

    db.commit()
    db.refresh(hour)
    return hour


@router.delete("/hours/{hour_id}")
def delete_operating_hour(
    hour_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """Real delete: an hour row has no history worth keeping."""
    hour = get_owned_hour(hour_id, db, current_user)
    db.delete(hour)
    db.commit()
    return {"message": "Operating hour deleted"}
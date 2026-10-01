from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from controllers.branches import can_manage, is_public_business
from controllers.businesses import get_owned_business
from database import get_db
from dependencies.get_optional_user import get_optional_user
from dependencies.roles import require_owner
from models.announcement import AnnouncementModel
from models.branch import BranchModel
from models.business import BusinessModel
from models.user import UserModel
from serializers.announcement import (
    AnnouncementCreateSchema,
    AnnouncementSchema,
    AnnouncementUpdateSchema,
)

router = APIRouter(tags=["Announcements"])


# ---------- helpers ----------

def get_owned_announcement(announcement_id: int, db: Session, user: UserModel) -> AnnouncementModel:
    """Find an announcement and make sure the logged-in owner owns its business."""
    announcement = db.query(AnnouncementModel).filter(AnnouncementModel.id == announcement_id).first()
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    if announcement.business.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your announcement")
    return announcement


def check_branch_belongs(db: Session, branch_id: Optional[int], business_id: int):
    """If a branch is given, it must be one of this business's branches."""
    if branch_id is None:
        return
    branch = db.query(BranchModel).filter(BranchModel.id == branch_id).first()
    if not branch or branch.business_id != business_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This branch doesn't belong to this business",
        )


# ---------- routes ----------

@router.get("/businesses/{business_id}/announcements", response_model=List[AnnouncementSchema])
def get_announcements(
    business_id: int,
    branch_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
):
    """Public: active announcements. With ?branch_id=, shows business-wide ones plus that branch's."""
    business = db.query(BusinessModel).filter(BusinessModel.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    manager = can_manage(current_user, business)
    if not manager and not is_public_business(business):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    query = db.query(AnnouncementModel).filter(AnnouncementModel.business_id == business_id)

    # The owner and admin also see deactivated announcements; the public doesn't
    if not manager:
        query = query.filter(AnnouncementModel.is_active.is_(True))

    if branch_id is not None:
        query = query.filter(
            or_(AnnouncementModel.branch_id.is_(None), AnnouncementModel.branch_id == branch_id)
        )

    return query.order_by(AnnouncementModel.created_at.desc()).all()


@router.post(
    "/businesses/{business_id}/announcements",
    response_model=AnnouncementSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_announcement(
    business_id: int,
    data: AnnouncementCreateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    business = get_owned_business(business_id, db, current_user)
    check_branch_belongs(db, data.branch_id, business.id)

    announcement = AnnouncementModel(
        business_id=business.id,
        branch_id=data.branch_id,
        title=data.title.strip(),
        message=data.message.strip(),
    )

    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementSchema)
def update_announcement(
    announcement_id: int,
    data: AnnouncementUpdateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    announcement = get_owned_announcement(announcement_id, db, current_user)
    changes = data.model_dump(exclude_unset=True)

    if "branch_id" in changes:
        check_branch_belongs(db, changes["branch_id"], announcement.business_id)

    for field, value in changes.items():
        if field in ("title", "message"):
            if value is None:
                continue  # can't be empty
            value = value.strip()
        if field == "is_active" and value is None:
            continue
        setattr(announcement, field, value)

    db.commit()
    db.refresh(announcement)
    return announcement


@router.delete("/announcements/{announcement_id}")
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """Deactivate (not a real delete). The owner can turn it back on with PATCH is_active: true."""
    announcement = get_owned_announcement(announcement_id, db, current_user)
    announcement.is_active = False
    db.commit()
    return {"message": "Announcement deactivated"}
# controllers/admin_suspicious_activity.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies.roles import require_admin
from models.audit_log import AuditLogModel
from models.suspicious_activity import SuspiciousActivityModel
from models.user import UserModel
from serializers.suspicious_activity import (
    ActivityStatus,
    Severity,
    SuspiciousActivitySchema,
    SuspiciousActivityUpdateSchema,
)

router = APIRouter(prefix="/admin/suspicious-activity", tags=["Admin: Suspicious Activity"])


def find_activity(db: Session, activity_id: int) -> SuspiciousActivityModel:
    activity = db.query(SuspiciousActivityModel).filter(SuspiciousActivityModel.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return activity


def activity_out(activity: SuspiciousActivityModel) -> SuspiciousActivitySchema:
    data = SuspiciousActivitySchema.model_validate(activity)
    data.user_name = activity.user.name
    data.user_email = activity.user.email
    data.user_no_show_count = activity.user.no_show_count
    data.user_restricted_until = activity.user.restricted_until
    data.queue_name = activity.queue.name if activity.queue else None
    data.reviewer_name = activity.reviewer.name if activity.reviewer else None
    return data


@router.get("", response_model=list[SuspiciousActivitySchema])
def get_suspicious_activity(
    status_filter: Optional[ActivityStatus] = Query(default=None, alias="status"),
    severity: Optional[Severity] = None,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    query = db.query(SuspiciousActivityModel)
    if status_filter:
        query = query.filter(SuspiciousActivityModel.status == status_filter)
    if severity:
        query = query.filter(SuspiciousActivityModel.severity == severity)

    activities = query.order_by(SuspiciousActivityModel.created_at.desc()).all()
    return [activity_out(activity) for activity in activities]


@router.get("/{activity_id}", response_model=SuspiciousActivitySchema)
def show_suspicious_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    return activity_out(find_activity(db, activity_id))


@router.patch("/{activity_id}", response_model=SuspiciousActivitySchema)
def update_suspicious_activity(
    activity_id: int,
    data: SuspiciousActivityUpdateSchema,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    activity = find_activity(db, activity_id)

    if data.status == activity.status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Already {data.status}")

    activity.status = data.status
    if data.status == "open":
        activity.reviewed_by = None
        activity.reviewed_at = None
    else:
        activity.reviewed_by = admin.id
        activity.reviewed_at = func.now()

    description = f"Marked {activity.activity_type} for {activity.user.email} as {data.status}"
    if data.note:
        description += f": {data.note}"

    db.add(
        AuditLogModel(
            admin_id=admin.id,
            action=f"suspicious_activity_{data.status}",
            entity_type="suspicious_activity",
            entity_id=activity.id,
            description=description,
        )
    )

    db.commit()
    db.refresh(activity)
    return activity_out(activity)
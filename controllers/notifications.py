# controllers/notifications.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies.get_current_user import get_current_user
from models.notification import NotificationModel
from models.user import UserModel
from serializers.notification import NotificationListSchema, NotificationSchema, NotificationUpdateSchema

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def find_my_notification(db: Session, notification_id: int, user: UserModel) -> NotificationModel:
    notification = (
        db.query(NotificationModel)
        .filter(NotificationModel.id == notification_id, NotificationModel.user_id == user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.get("", response_model=NotificationListSchema)
def get_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    unread_count = (
        db.query(NotificationModel)
        .filter(NotificationModel.user_id == user.id, NotificationModel.is_read.is_(False))
        .count()
    )

    query = db.query(NotificationModel).filter(NotificationModel.user_id == user.id)
    if unread_only:
        query = query.filter(NotificationModel.is_read.is_(False))

    notifications = query.order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc()).all()
    return {"unread_count": unread_count, "notifications": notifications}


# This must stay ABOVE /{notification_id}
@router.patch("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    updated = (
        db.query(NotificationModel)
        .filter(NotificationModel.user_id == user.id, NotificationModel.is_read.is_(False))
        .update({NotificationModel.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return {"message": "All notifications marked as read", "updated": updated}


@router.patch("/{notification_id}", response_model=NotificationSchema)
def update_notification(
    notification_id: int,
    data: NotificationUpdateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    notification = find_my_notification(db, notification_id, user)
    notification.is_read = data.is_read
    db.commit()
    db.refresh(notification)
    return notification


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    notification = find_my_notification(db, notification_id, user)
    db.delete(notification)
    db.commit()
    return {"message": "Notification deleted"}
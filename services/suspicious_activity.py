# services/suspicious_activity.py
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.queue import QueueModel
from models.queue_entry import QueueEntryModel
from models.suspicious_activity import SuspiciousActivityModel
from models.user import UserModel

FLAG_COOLDOWN_HOURS = 24  # don't repeat the same open flag within this time
CANCEL_LIMIT = 3  # this many cancelled tickets...
CANCEL_WINDOW_MINUTES = 60  # ...within this many minutes gets flagged


def flag_activity(
    db: Session,
    user: UserModel,
    activity_type: str,
    description: str,
    severity: str = "low",
    queue: QueueModel | None = None,
):
    """Create a suspicious activity record, unless the same one is already open."""
    already_open = (
        db.query(SuspiciousActivityModel.id)
        .filter(
            SuspiciousActivityModel.user_id == user.id,
            SuspiciousActivityModel.activity_type == activity_type,
            SuspiciousActivityModel.status == "open",
            SuspiciousActivityModel.created_at >= func.now() - timedelta(hours=FLAG_COOLDOWN_HOURS),
        )
        .first()
    )
    if already_open:
        return None

    activity = SuspiciousActivityModel(
        user_id=user.id,
        queue_id=queue.id if queue else None,
        activity_type=activity_type,
        description=description,
        severity=severity,
    )
    db.add(activity)
    return activity


def check_frequent_cancellations(db: Session, user: UserModel, queue: QueueModel):
    """Call after a cancel has been flushed."""
    recent_cancels = (
        db.query(QueueEntryModel)
        .filter(
            QueueEntryModel.user_id == user.id,
            QueueEntryModel.status == "cancelled",
            QueueEntryModel.cancelled_at >= func.now() - timedelta(minutes=CANCEL_WINDOW_MINUTES),
        )
        .count()
    )
    if recent_cancels >= CANCEL_LIMIT:
        flag_activity(
            db,
            user,
            "frequent_cancellations",
            f"Left {recent_cancels} queues in the last {CANCEL_WINDOW_MINUTES} minutes.",
            severity="low",
            queue=queue,
        )
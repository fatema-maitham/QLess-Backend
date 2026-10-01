# services/notifications.py
from sqlalchemy.orm import Session

from models.notification import NotificationModel
from models.queue import QueueModel
from models.queue_entry import QueueEntryModel
from models.user import UserModel

TURN_APPROACHING_POSITION = 3  # warn people when they reach the top 3


def notify(user: UserModel, type_: str, title: str, message: str | None = None):
    """Add a notification for a user. The route's db.commit() saves it."""
    user.notifications.append(NotificationModel(type=type_, title=title, message=message))


def notify_turn_approaching(db: Session, queue: QueueModel):
    """Warn the first few waiting people that their turn is close (only once per ticket)."""
    next_up = (
        db.query(QueueEntryModel)
        .filter(QueueEntryModel.queue_id == queue.id, QueueEntryModel.status == "waiting")
        .order_by(QueueEntryModel.queue_number)
        .limit(TURN_APPROACHING_POSITION)
        .all()
    )

    for position, entry in enumerate(next_up, start=1):
        tag = f"Ticket #{entry.queue_number} at {queue.name}"

        already_sent = (
            db.query(NotificationModel.id)
            .filter(
                NotificationModel.user_id == entry.user_id,
                NotificationModel.type == "turn_approaching",
                NotificationModel.message.startswith(tag),
                NotificationModel.created_at >= entry.joined_at,
            )
            .first()
        )
        if already_sent:
            continue

        ahead = position - 1
        people = "person" if ahead == 1 else "people"
        notify(
            entry.user,
            "turn_approaching",
            "Your turn is coming up",
            f"{tag}: {ahead} {people} ahead of you. Start heading over.",
        )
# services/no_shows.py
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.queue_entry import QueueEntryModel
from services.notifications import notify
from services.suspicious_activity import flag_activity

NO_SHOWS_BEFORE_RESTRICTION = 3
RESTRICTION_DAYS = 7


def handle_no_show(db: Session, entry: QueueEntryModel):
    """Mark the no-show, then warn or restrict the customer."""
    user = entry.user
    queue = entry.queue

    entry.no_show_at = func.now()
    user.no_show_count += 1
    count = user.no_show_count

    notify(
        user,
        "no_show",
        "You missed your turn",
        f"Ticket #{entry.queue_number} at {queue.name} was marked as a no-show.",
    )

    strikes = count % NO_SHOWS_BEFORE_RESTRICTION

    if strikes == NO_SHOWS_BEFORE_RESTRICTION - 1:
        notify(
            user,
            "no_show_warning",
            "Warning: one more no-show",
            f"You have missed {count} turns. One more and you won't be able to join "
            f"queues for {RESTRICTION_DAYS} days.",
        )

    elif strikes == 0:
        user.restricted_until = func.now() + timedelta(days=RESTRICTION_DAYS)
        notify(
            user,
            "restricted",
            "Your account is restricted",
            f"You missed {count} turns, so you can't join queues for {RESTRICTION_DAYS} days.",
        )
        flag_activity(
            db,
            user,
            "repeated_no_show",
            f"{count} no-shows in total. Restricted for {RESTRICTION_DAYS} days.",
            severity="high" if count >= NO_SHOWS_BEFORE_RESTRICTION * 2 else "medium",
            queue=queue,
        )
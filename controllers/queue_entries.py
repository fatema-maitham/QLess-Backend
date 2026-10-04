# controllers/queue_entries.py
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from dependencies.get_current_user import get_current_user
from dependencies.queue_access import check_owner_or_staff, find_queue, owns_business, works_at_branch
from dependencies.roles import require_customer, require_owner_or_staff
from models.queue_entry import QueueEntryModel
from models.user import UserModel
from realtime.queue_updates import broadcast, queue_message
from serializers.queue_entry import (
    EntryStatus,
    MyQueueEntriesSchema,
    QueueEntrySchema,
    QueueEntryUpdateSchema,
)
from services.no_shows import handle_no_show
from services.suspicious_activity import check_frequent_cancellations

router = APIRouter(tags=["Queue Entries"])

ACTIVE_STATUSES = ["waiting", "called", "checked_in"]
IN_LINE_STATUSES = ["waiting", "called"]
ARRIVE_EARLY_MINUTES = 10

# Owner/staff: which status an entry must have before it can move to the new one
MANAGER_MOVES = {
    "checked_in": {"called"},
    "completed": {"called", "checked_in"},
    "no_show": {"called"},
}


# ---------- Helpers ----------

def find_entry(db: Session, entry_id: int) -> QueueEntryModel:
    entry = db.query(QueueEntryModel).filter(QueueEntryModel.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue entry not found")
    return entry


def can_manage(db: Session, user: UserModel, entry: QueueEntryModel) -> bool:
    queue = entry.queue
    return owns_business(user, queue.business) or works_at_branch(db, user, queue.branch_id)


def entry_out(db: Session, entry: QueueEntryModel) -> QueueEntrySchema:
    queue = entry.queue
    data = QueueEntrySchema.model_validate(entry)

    data.customer_name = entry.user.name
    data.queue_name = queue.name
    data.queue_status = queue.status
    data.current_number = queue.current_number
    data.branch_id = queue.branch_id
    data.branch_name = queue.branch.name
    data.business_name = queue.business.name

    now = datetime.now(timezone.utc)

    if entry.status == "waiting":
        ahead = (
            db.query(QueueEntryModel)
            .filter(
                QueueEntryModel.queue_id == queue.id,
                QueueEntryModel.status == "waiting",
                QueueEntryModel.queue_number < entry.queue_number,
            )
            .count()
        )
        # With more than one counter, several people are served at the same time
        rounds = ahead // max(queue.counter_count or 1, 1)        wait = rounds * queue.average_service_minutes
        data.people_ahead = ahead
        data.position = ahead + 1
        data.estimated_wait_minutes = wait
        data.recommended_return_time = now + timedelta(minutes=max(wait - ARRIVE_EARLY_MINUTES, 0))

    elif entry.status == "called":
        data.people_ahead = 0
        data.position = 0
        data.estimated_wait_minutes = 0
        data.recommended_return_time = now

    return data


# ---------- Join a queue ----------

@router.post("/queues/{queue_id}/entries", response_model=QueueEntrySchema, status_code=status.HTTP_201_CREATED)
def create_queue_entry(
    queue_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    queue = find_queue(db, queue_id)

    if queue.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This queue is not open right now")

    # The business must be approved and active, and the branch active
    business = queue.business
    if business.approval_status != "approved" or not business.is_active or not queue.branch.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This place isn't taking customers right now")

    # Compare in the database so the time zones always match
    restricted_until = (
        db.query(UserModel.restricted_until)
        .filter(UserModel.id == user.id, UserModel.restricted_until > func.now())
        .scalar()
    )
    if restricted_until:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can't join queues until {restricted_until:%d %b %Y, %H:%M} because of repeated no-shows",
        )

    already_in = (
        db.query(QueueEntryModel)
        .filter(
            QueueEntryModel.queue_id == queue.id,
            QueueEntryModel.user_id == user.id,
            QueueEntryModel.status.in_(ACTIVE_STATUSES),
        )
        .first()
    )
    if already_in:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You're already in this queue")

    if queue.max_capacity is not None:
        in_line = (
            db.query(QueueEntryModel)
            .filter(QueueEntryModel.queue_id == queue.id, QueueEntryModel.status.in_(IN_LINE_STATUSES))
            .count()
        )
        if in_line >= queue.max_capacity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This queue is full")

    last_number = (
        db.query(func.max(QueueEntryModel.queue_number)).filter(QueueEntryModel.queue_id == queue.id).scalar() or 0
    )

    entry = QueueEntryModel(queue_id=queue.id, user_id=user.id, queue_number=last_number + 1, status="waiting")
    db.add(entry)

    try:
        db.commit()
    except IntegrityError:
        # Two people got the same number at the same moment
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Someone joined at the same time. Please try again")

    db.refresh(entry)
    broadcast(queue.id, queue_message(db, queue, "entry_joined", entry_id=entry.id))
    return entry_out(db, entry)


# ---------- Owner/staff: list entries in a queue ----------

@router.get("/queues/{queue_id}/entries", response_model=list[QueueEntrySchema])
def get_queue_entries(
    queue_id: int,
    status_filter: Optional[EntryStatus] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_owner_or_staff),
):
    queue = find_queue(db, queue_id)
    check_owner_or_staff(db, user, queue)

    query = db.query(QueueEntryModel).filter(QueueEntryModel.queue_id == queue.id)
    if status_filter:
        query = query.filter(QueueEntryModel.status == status_filter)

    entries = query.order_by(QueueEntryModel.queue_number).all()
    return [entry_out(db, entry) for entry in entries]


# ---------- Customer: my tickets ----------
# This must stay ABOVE /queue-entries/{entry_id}

@router.get("/queue-entries/me", response_model=MyQueueEntriesSchema)
def get_my_queue_entries(
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    entries = (
        db.query(QueueEntryModel)
        .filter(QueueEntryModel.user_id == user.id)
        .order_by(QueueEntryModel.joined_at.desc())
        .all()
    )
    return {
        "active": [entry_out(db, entry) for entry in entries if entry.status in ACTIVE_STATUSES],
        "history": [entry_out(db, entry) for entry in entries if entry.status not in ACTIVE_STATUSES],
    }


# ---------- One ticket ----------

@router.get("/queue-entries/{entry_id}", response_model=QueueEntrySchema)
def show_queue_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    entry = find_entry(db, entry_id)
    if entry.user_id != user.id and not can_manage(db, user, entry):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't see this ticket")
    return entry_out(db, entry)


def customer_update(entry: QueueEntryModel, updates: dict):
    if "on_the_way" in updates:
        if entry.status not in IN_LINE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You can only mark 'on the way' while waiting or called",
            )
        entry.on_the_way = bool(updates["on_the_way"])

    new_status = updates.get("status")
    if new_status is None:
        return

    if new_status != "checked_in":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customers can only check in")
    if entry.status != "called":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can check in after you are called")

    entry.status = "checked_in"
    entry.checked_in_at = func.now()


def manager_update(db: Session, entry: QueueEntryModel, updates: dict):
    if "on_the_way" in updates:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the customer can mark 'on the way'")

    new_status = updates.get("status")
    if new_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Send a status")

    if entry.status not in MANAGER_MOVES[new_status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can't mark a {entry.status} ticket as {new_status}",
        )

    entry.status = new_status

    if new_status == "checked_in":
        entry.checked_in_at = func.now()

    elif new_status == "completed":
        if entry.checked_in_at is None:
            entry.checked_in_at = func.now()
        entry.completed_at = func.now()

    elif new_status == "no_show":
        handle_no_show(db, entry)


@router.patch("/queue-entries/{entry_id}", response_model=QueueEntrySchema)
def update_queue_entry(
    entry_id: int,
    data: QueueEntryUpdateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    entry = find_entry(db, entry_id)

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")

    if entry.user_id == user.id:
        customer_update(entry, updates)
    elif can_manage(db, user, entry):
        manager_update(db, entry, updates)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't change this ticket")

    db.commit()
    db.refresh(entry)

    broadcast(
        entry.queue_id,
        queue_message(
            db, entry.queue, "entry_updated",
            entry_id=entry.id, entry_status=entry.status, on_the_way=entry.on_the_way,
        ),
    )
    return entry_out(db, entry)


# ---------- Leave a queue ----------

@router.delete("/queue-entries/{entry_id}")
def delete_queue_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    entry = find_entry(db, entry_id)

    if entry.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This isn't your ticket")
    if entry.status not in IN_LINE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This ticket is already finished")

    entry.status = "cancelled"
    entry.on_the_way = False
    entry.cancelled_at = func.now()

    # Save the cancel first so it is counted, then check for too many cancels
    db.flush()
    check_frequent_cancellations(db, user, entry.queue)

    db.commit()
    broadcast(entry.queue_id, queue_message(db, entry.queue, "entry_left", entry_id=entry.id))
    return {"message": "You left the queue"}
# controllers/queues.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies.queue_access import (
    check_owner,
    check_owner_or_staff,
    find_branch,
    find_queue,
    owns_business,
)
from dependencies.roles import require_owner, require_owner_or_staff
from models.queue import QueueModel
from models.queue_entry import QueueEntryModel
from models.service import ServiceModel
from models.user import UserModel
from realtime.queue_updates import broadcast, queue_message
from serializers.queue import (
    CallNextResponseSchema,
    CallNextSchema,
    QueueAnalyticsSchema,
    QueueCreateSchema,
    QueueSchema,
    QueueUpdateSchema,
    ServingSchema,
)
from services.notifications import notify, notify_turn_approaching

router = APIRouter(tags=["Queues"])

# Which status a queue can move to from its current status
ALLOWED_MOVES = {
    "closed": {"open"},
    "open": {"paused", "closed"},
    "paused": {"open", "closed"},  # paused -> open is "resume"
}


def count_waiting(db: Session, queue_id: int) -> int:
    return (
        db.query(QueueEntryModel)
        .filter(QueueEntryModel.queue_id == queue_id, QueueEntryModel.status == "waiting")
        .count()
    )


def serving_now(db: Session, queue_id: int) -> list[ServingSchema]:
    """Tickets at a counter right now (called or checked in), by counter."""
    entries = (
        db.query(QueueEntryModel)
        .filter(QueueEntryModel.queue_id == queue_id, QueueEntryModel.status.in_(["called", "checked_in"]))
        .order_by(QueueEntryModel.counter_number, QueueEntryModel.queue_number)
        .all()
    )
    return [
        ServingSchema(
            counter_number=entry.counter_number or 1,
            queue_number=entry.queue_number,
            status=entry.status,
        )
        for entry in entries
    ]


def queue_out(db: Session, queue: QueueModel) -> QueueSchema:
    data = QueueSchema.model_validate(queue)
    data.waiting_count = count_waiting(db, queue.id)
    data.now_serving = serving_now(db, queue.id)
    return data


def check_service_in_branch(db: Session, service_id: int, branch_id: int):
    service = (
        db.query(ServiceModel)
        .filter(ServiceModel.id == service_id, ServiceModel.branch_id == branch_id)
        .first()
    )
    if not service:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That service is not in this branch")


def change_status(queue: QueueModel, new_status: str):
    if new_status == queue.status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Queue is already {new_status}")

    if new_status not in ALLOWED_MOVES[queue.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can't change a {queue.status} queue to {new_status}",
        )

    if new_status == "open":
        business = queue.business
        if business.approval_status != "approved" or not business.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The business must be approved and active before opening a queue",
            )
        if not queue.branch.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This branch is deactivated")

    queue.status = new_status


# ---------- List and create queues for a branch ----------

@router.get("/branches/{branch_id}/queues", response_model=list[QueueSchema])
def get_queues(branch_id: int, db: Session = Depends(get_db)):
    find_branch(db, branch_id)
    queues = db.query(QueueModel).filter(QueueModel.branch_id == branch_id).order_by(QueueModel.name).all()
    return [queue_out(db, queue) for queue in queues]


@router.post("/branches/{branch_id}/queues", response_model=QueueSchema, status_code=status.HTTP_201_CREATED)
def create_queue(
    branch_id: int,
    data: QueueCreateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_owner),
):
    branch = find_branch(db, branch_id)
    check_owner(user, branch.business)

    if data.service_id is not None:
        check_service_in_branch(db, data.service_id, branch.id)

    queue = QueueModel(
        business_id=branch.business_id,
        branch_id=branch.id,
        service_id=data.service_id,
        name=data.name.strip(),
        max_capacity=data.max_capacity,
        average_service_minutes=data.average_service_minutes,
        no_show_grace_minutes=data.no_show_grace_minutes,
        counter_count=data.counter_count,
        status="closed",  # owner opens it when ready
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue_out(db, queue)


# ---------- One queue ----------

@router.get("/queues/{queue_id}", response_model=QueueSchema)
def show_queue(queue_id: int, db: Session = Depends(get_db)):
    return queue_out(db, find_queue(db, queue_id))


@router.patch("/queues/{queue_id}", response_model=QueueSchema)
def update_queue(
    queue_id: int,
    data: QueueUpdateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_owner_or_staff),
):
    queue = find_queue(db, queue_id)
    check_owner_or_staff(db, user, queue)

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")

    # Staff can only open / pause / resume / close
    if not owns_business(user, queue.business) and set(updates) != {"status"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff can only change the queue status")

    new_status = updates.pop("status", None)

    if "service_id" in updates and updates["service_id"] is not None:
        check_service_in_branch(db, updates["service_id"], queue.branch_id)

    if "name" in updates:
        updates["name"] = updates["name"].strip()


    # Don't remove a counter that is still serving someone
    if updates.get("counter_count") is not None:
        highest_busy = (
            db.query(func.max(QueueEntryModel.counter_number))
            .filter(QueueEntryModel.queue_id == queue.id, QueueEntryModel.status.in_(["called", "checked_in"]))
            .scalar()
        )
        if highest_busy and updates["counter_count"] < highest_busy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Counter {highest_busy} is still serving someone. Finish that ticket before removing the counter",
            )
    for field, value in updates.items():
        setattr(queue, field, value)

    if new_status is not None:
        change_status(queue, new_status)

    db.commit()
    db.refresh(queue)

    event = "queue_status_changed" if new_status is not None else "queue_updated"
    broadcast(queue.id, queue_message(db, queue, event))

    return queue_out(db, queue)


@router.delete("/queues/{queue_id}")
def delete_queue(
    queue_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_owner),
):
    queue = find_queue(db, queue_id)
    check_owner(user, queue.business)

    active = (
        db.query(QueueEntryModel)
        .filter(QueueEntryModel.queue_id == queue.id, QueueEntryModel.status.in_(["waiting", "called"]))
        .count()
    )
    if active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="People are still waiting in this queue. Close it and serve them first",
        )

    queue_id = queue.id
    db.delete(queue)
    db.commit()
    broadcast(queue_id, {"type": "queue_deleted", "queue_id": queue_id})
    return {"message": "Queue deleted"}


# ---------- Call next ----------

@router.post("/queues/{queue_id}/call-next", response_model=CallNextResponseSchema)
def call_next(
    queue_id: int,
    data: Optional[CallNextSchema] = None,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_owner_or_staff),
):
    queue = find_queue(db, queue_id)
    check_owner_or_staff(db, user, queue)

    if queue.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Open the queue before calling the next person")

    # Owners may operate any counter. Staff always use the counter assigned
    # to them by the owner; their job title (e.g. Teller) is separate.
    if user.role.name == "staff":
        from models.staff import StaffModel

        assignment = (
            db.query(StaffModel)
            .filter(
                StaffModel.user_id == user.id,
                StaffModel.branch_id == queue.branch_id,
                StaffModel.is_active.is_(True),
            )
            .first()
        )
        if not assignment:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not assigned to this branch")
        counter = assignment.counter_number
    else:
        counter = data.counter_number if data else 1

    if counter > queue.counter_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This queue has {queue.counter_count} counter(s). Pick a counter from 1 to {queue.counter_count}",
        )

    # A counter serves one person at a time
    still_serving = (
        db.query(QueueEntryModel)
        .filter(
            QueueEntryModel.queue_id == queue.id,
            QueueEntryModel.counter_number == counter,
            QueueEntryModel.status.in_(["called", "checked_in"]),
        )
        .first()
    )
    if still_serving:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Counter {counter} is still serving number {still_serving.queue_number}. "
            "Mark it completed or no-show first",
        )

    entry = (
        db.query(QueueEntryModel)
        .filter(QueueEntryModel.queue_id == queue.id, QueueEntryModel.status == "waiting")
        .order_by(QueueEntryModel.queue_number)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No one is waiting")

    entry.status = "called"
    entry.called_at = func.now()
    entry.counter_number = counter
    queue.current_number = entry.queue_number

    notify(
        entry.user,
        "called",
        "It's your turn!",
        f"Ticket #{entry.queue_number} at {queue.name}: please come to counter {counter} "
        f"within {queue.no_show_grace_minutes} minutes.",
    )

    # Save the "called" change first so the next waiting people are counted correctly
    db.flush()
    notify_turn_approaching(db, queue)

    db.commit()
    db.refresh(entry)
    db.refresh(queue)

    broadcast(
        queue.id,
        queue_message(
            db, queue, "entry_called",
            entry_id=entry.id, user_id=entry.user_id, queue_number=entry.queue_number,
            counter_number=counter,
        ),
    )

    return {
        "message": f"Called number {entry.queue_number} to counter {counter}",
        "queue": queue_out(db, queue),
        "entry": entry,
    }


# ---------- Analytics ----------

def average_minutes(pairs):
    minutes = [(end - start).total_seconds() / 60 for start, end in pairs if start and end]
    return round(sum(minutes) / len(minutes), 1) if minutes else None


@router.get("/queues/{queue_id}/analytics", response_model=QueueAnalyticsSchema)
def get_queue_analytics(
    queue_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_owner),
):
    queue = find_queue(db, queue_id)
    check_owner(user, queue.business)

    entries = queue.entries
    counts = {name: 0 for name in ["waiting", "called", "checked_in", "completed", "cancelled", "no_show"]}
    for entry in entries:
        if entry.status in counts:
            counts[entry.status] += 1

    finished = counts["completed"] + counts["no_show"]
    no_show_rate = round(counts["no_show"] / finished * 100, 1) if finished else 0.0

    return {
        "queue_id": queue.id,
        "total_entries": len(entries),
        **counts,
        "no_show_rate": no_show_rate,
        "average_wait_minutes": average_minutes((e.joined_at, e.called_at) for e in entries),
        "average_service_minutes": average_minutes(
            (e.checked_in_at, e.completed_at) for e in entries if e.status == "completed"
        ),
    }
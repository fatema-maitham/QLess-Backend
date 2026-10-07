from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.branch import BranchModel
from models.business import BusinessModel
from models.queue import QueueModel
from models.staff import StaffModel
from models.user import UserModel


def find_branch(db: Session, branch_id: int) -> BranchModel:
    branch = (
        db.query(BranchModel)
        .filter(BranchModel.id == branch_id)
        .first()
    )

    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )

    return branch


def find_queue(db: Session, queue_id: int) -> QueueModel:
    queue = (
        db.query(QueueModel)
        .filter(QueueModel.id == queue_id)
        .first()
    )

    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue not found",
        )

    return queue


def owns_business(
    user: UserModel,
    business: BusinessModel,
) -> bool:
    return (
        user.role.name == "owner"
        and business.owner_id == user.id
    )


def works_at_branch(
    db: Session,
    user: UserModel,
    branch_id: int,
) -> bool:
    """
    Branch-level staff permission.

    Use this only for functionality that belongs to the
    whole branch, such as branch bookings.
    """
    if user.role.name != "staff":
        return False

    assignment = (
        db.query(StaffModel)
        .filter(
            StaffModel.user_id == user.id,
            StaffModel.branch_id == branch_id,
            StaffModel.is_active.is_(True),
        )
        .first()
    )

    return assignment is not None


def assigned_to_queue(
    db: Session,
    user: UserModel,
    queue: QueueModel,
) -> bool:
    """
    Queue-level staff permission.

    Staff must be active and assigned to this exact
    branch and queue.
    """
    if user.role.name != "staff":
        return False

    assignment = (
        db.query(StaffModel)
        .filter(
            StaffModel.user_id == user.id,
            StaffModel.branch_id == queue.branch_id,
            StaffModel.queue_id == queue.id,
            StaffModel.is_active.is_(True),
        )
        .first()
    )

    return assignment is not None


def check_owner(
    user: UserModel,
    business: BusinessModel,
):
    if not owns_business(user, business):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this business",
        )


def check_owner_or_staff(
    db: Session,
    user: UserModel,
    queue: QueueModel,
):
    """
    Owners can access queues belonging to their business.

    Staff can access only the exact queue assigned
    to them.
    """
    if owns_business(user, queue.business):
        return

    if assigned_to_queue(db, user, queue):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not assigned to this queue",
    )
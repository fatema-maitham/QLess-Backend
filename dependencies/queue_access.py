# dependencies/queue_access.py
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.branch import BranchModel
from models.business import BusinessModel
from models.queue import QueueModel
from models.staff import StaffModel
from models.user import UserModel


def find_branch(db: Session, branch_id: int) -> BranchModel:
    branch = db.query(BranchModel).filter(BranchModel.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


def find_queue(db: Session, queue_id: int) -> QueueModel:
    queue = db.query(QueueModel).filter(QueueModel.id == queue_id).first()
    if not queue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found")
    return queue


def owns_business(user: UserModel, business: BusinessModel) -> bool:
    return user.role.name == "owner" and business.owner_id == user.id


def works_at_branch(db: Session, user: UserModel, branch_id: int) -> bool:
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


def check_owner(user: UserModel, business: BusinessModel):
    if not owns_business(user, business):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't own this business")


def check_owner_or_staff(db: Session, user: UserModel, queue: QueueModel):
    if owns_business(user, queue.business) or works_at_branch(db, user, queue.branch_id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't manage this queue")
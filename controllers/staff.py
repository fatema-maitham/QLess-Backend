from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from controllers.branches import get_owned_branch
from database import get_db
from dependencies.roles import require_owner, require_staff
from models.queue_entry import QueueEntryModel
from models.queue import QueueModel
from models.role import RoleModel
from models.staff import StaffModel
from models.user import UserModel
from serializers.staff import (
    StaffBranchSchema,
    StaffBusinessSchema,
    StaffCreateSchema,
    StaffMeSchema,
    StaffQueueSchema,
    StaffSchema,
    StaffUpdateSchema,
)


router = APIRouter(tags=["Staff"])


# ---------- helpers ----------


def set_role(
    db: Session,
    user: UserModel,
    role_name: str,
):
    role = (
        db.query(RoleModel)
        .filter(RoleModel.name == role_name)
        .first()
    )

    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Roles are missing. Run seed.py",
        )

    user.role = role


def get_owned_staff(
    staff_id: int,
    db: Session,
    user: UserModel,
) -> StaffModel:
    """
    Find a staff record and make sure
    the logged-in owner owns its business.
    """

    staff = (
        db.query(StaffModel)
        .filter(StaffModel.id == staff_id)
        .first()
    )

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )

    if staff.business.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is not your staff member",
        )

    return staff


def has_other_active_assignment(
    db: Session,
    user_id: int,
    ignore_id: int,
) -> bool:
    return (
        db.query(StaffModel)
        .filter(
            StaffModel.user_id == user_id,
            StaffModel.is_active.is_(True),
            StaffModel.id != ignore_id,
        )
        .first()
        is not None
    )


def get_active_ticket_for_staff(
    db: Session,
    staff: StaffModel,
):
    """
    Find a called/checked-in ticket currently being
    served at this staff member's assigned counter.
    """

    if not staff.is_active:
        return None

    return (
        db.query(QueueEntryModel)
        .filter(
            QueueEntryModel.branch_id == staff.branch_id,
            QueueEntryModel.counter_number == staff.counter_number,
            QueueEntryModel.status.in_(
                ["called", "checked_in"]
            ),
        )
        .first()
    )


def ensure_not_serving(
    db: Session,
    staff: StaffModel,
):
    """
    Do not allow assignment changes or deactivation
    while the staff member is serving someone.
    """

    active_ticket = get_active_ticket_for_staff(
        db,
        staff,
    )

    if active_ticket:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This staff member is currently serving "
                f"ticket #{active_ticket.queue_number} at "
                f"counter {staff.counter_number}. "
                "Complete or finish the ticket before "
                "changing the assignment or deactivating staff."
            ),
        )


def deactivate_staff(
    db: Session,
    staff: StaffModel,
):
    staff.is_active = False

    # If they don't work anywhere else,
    # they become a normal customer again.
    if not has_other_active_assignment(
        db,
        staff.user_id,
        staff.id,
    ):
        set_role(
            db,
            staff.user,
            "customer",
        )


def validate_staff_assignment(
    db: Session,
    branch_id: int,
    queue_id: Optional[int],
    counter_number: int,
):
    if queue_id is None:
        return

    queue = (
        db.query(QueueModel)
        .filter(
            QueueModel.id == queue_id,
            QueueModel.branch_id == branch_id,
        )
        .first()
    )

    if not queue:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a queue belonging to this branch",
        )

    if not 1 <= counter_number <= queue.counter_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Choose a counter from 1 to {queue.counter_count}",
        )


# ---------- routes ----------
# /staff/me must come BEFORE /staff/{staff_id},
# otherwise "me" is read as an id.


@router.get(
    "/staff/me",
    response_model=StaffMeSchema,
)
def get_me_staff(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_staff),
):
    """
    The staff member's assigned
    business, branch and queues.
    """

    staff = (
        db.query(StaffModel)
        .filter(
            StaffModel.user_id == current_user.id,
            StaffModel.is_active.is_(True),
        )
        .first()
    )

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not assigned to a branch yet",
        )

    return StaffMeSchema(
        id=staff.id,
        queue_id=staff.queue_id,
        position=staff.position,
        counter_number=staff.counter_number,
        business=StaffBusinessSchema.model_validate(
            staff.business
        ),
        branch=StaffBranchSchema.model_validate(
            staff.branch
        ),
        queues=[
            StaffQueueSchema.model_validate(queue)
            for queue in staff.branch.queues
        ],
    )


@router.get(
    "/branches/{branch_id}/staff",
    response_model=List[StaffSchema],
)
def get_staff(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    branch = get_owned_branch(
        branch_id,
        db,
        current_user,
    )

    return (
        db.query(StaffModel)
        .filter(
            StaffModel.branch_id == branch.id
        )
        .order_by(
            StaffModel.created_at.desc()
        )
        .all()
    )


@router.post(
    "/branches/{branch_id}/staff",
    response_model=StaffSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_staff(
    branch_id: int,
    data: StaffCreateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    branch = get_owned_branch(
        branch_id,
        db,
        current_user,
    )

    validate_staff_assignment(
        db,
        branch.id,
        data.queue_id,
        data.counter_number,
    )

    user = (
        db.query(UserModel)
        .filter(
            UserModel.email == data.user_email
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No account with this email. "
                "They need to sign up first."
            ),
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can't add yourself as staff",
        )

    if user.role.name not in (
        "customer",
        "staff",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only customer or staff accounts "
                "can be added as staff"
            ),
        )

    existing = (
        db.query(StaffModel)
        .filter(
            StaffModel.user_id == user.id,
            StaffModel.is_active.is_(True),
        )
        .first()
    )

    if existing:
        where = (
            "this branch"
            if existing.branch_id == branch.id
            else "another branch"
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This person is already staff at {where}",
        )

    staff = StaffModel(
        user_id=user.id,
        business_id=branch.business_id,
        branch_id=branch.id,
        queue_id=data.queue_id,
        position=data.position,
        counter_number=data.counter_number,
    )

    set_role(
        db,
        user,
        "staff",
    )

    db.add(staff)
    db.commit()
    db.refresh(staff)

    return staff


@router.get(
    "/staff/{staff_id}",
    response_model=StaffSchema,
)
def show_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    return get_owned_staff(
        staff_id,
        db,
        current_user,
    )


@router.patch(
    "/staff/{staff_id}",
    response_model=StaffSchema,
)
def update_staff(
    staff_id: int,
    data: StaffUpdateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    staff = get_owned_staff(
        staff_id,
        db,
        current_user,
    )

    changes = data.model_dump(
        exclude_unset=True
    )

    # Block assignment changes while the staff member
    # is actively serving a customer.
    assignment_changed = (
        (
            "counter_number" in changes
            and changes["counter_number"] != staff.counter_number
        )
        or (
            "queue_id" in changes
            and changes["queue_id"] != staff.queue_id
        )
    )

    if assignment_changed:
        ensure_not_serving(
            db,
            staff,
        )

    # Deactivation is also blocked while serving.
    if (
        changes.get("is_active") is False
        and staff.is_active
    ):
        ensure_not_serving(
            db,
            staff,
        )

    if (
        "counter_number" in changes
        and changes["counter_number"] is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Counter cannot be empty",
        )

    next_queue_id = changes.get(
        "queue_id",
        staff.queue_id,
    )

    next_counter = changes.get(
        "counter_number",
        staff.counter_number,
    )

    validate_staff_assignment(
        db,
        staff.branch_id,
        next_queue_id,
        next_counter,
    )

    if "queue_id" in changes:
        staff.queue_id = next_queue_id

    if "position" in changes:
        staff.position = changes["position"]

    if "counter_number" in changes:
        staff.counter_number = changes["counter_number"]

    new_active = changes.get("is_active")

    if (
        new_active is True
        and not staff.is_active
    ):
        # Reactivating: they cannot already be active
        # at another branch.
        if has_other_active_assignment(
            db,
            staff.user_id,
            staff.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This person is already active "
                    "staff at another branch"
                ),
            )

        if staff.user.role.name not in (
            "customer",
            "staff",
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Only customer or staff accounts "
                    "can be staff"
                ),
            )

        staff.is_active = True

        set_role(
            db,
            staff.user,
            "staff",
        )

    elif (
        new_active is False
        and staff.is_active
    ):
        deactivate_staff(
            db,
            staff,
        )

    db.commit()
    db.refresh(staff)

    return staff


@router.delete("/staff/{staff_id}")
def delete_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """
    Deactivate (not a real delete).
    The person goes back to being a customer
    if they have no other active staff assignment.
    """

    staff = get_owned_staff(
        staff_id,
        db,
        current_user,
    )

    if staff.is_active:
        # DELETE is another way to deactivate staff,
        # so it must use the same serving protection.
        ensure_not_serving(
            db,
            staff,
        )

        deactivate_staff(
            db,
            staff,
        )

        db.commit()

    return {
        "message": "Staff member deactivated"
    }
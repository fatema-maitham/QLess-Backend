# controllers/bookings.py

from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies.get_current_user import get_current_user
from dependencies.queue_access import (
    find_branch,
    owns_business,
    works_at_branch,
)
from dependencies.roles import (
    require_customer,
    require_owner_or_staff,
)
from models.booking import BookingModel
from models.branch import BranchModel
from models.operating_hour import OperatingHourModel
from models.service import ServiceModel
from models.user import UserModel
from serializers.booking import (
    AvailableSlotsSchema,
    BookingCreateSchema,
    BookingSchema,
    BookingStatus,
    BookingUpdateSchema,
)
from services.notifications import notify


router = APIRouter(tags=["Bookings"])


# A booking blocks its time while it is confirmed.
OPEN_STATUSES = ["confirmed"]

# Old services that do not have a duration yet
# will temporarily use 15 minutes.
DEFAULT_DURATION_MINUTES = 15


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def find_service(
    db: Session,
    service_id: int,
) -> ServiceModel:

    service = (
        db.query(ServiceModel)
        .filter(ServiceModel.id == service_id)
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    return service


def find_booking(
    db: Session,
    booking_id: int,
) -> BookingModel:

    booking = (
        db.query(BookingModel)
        .filter(BookingModel.id == booking_id)
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )

    return booking


def can_manage_branch(
    db: Session,
    user: UserModel,
    branch: BranchModel,
) -> bool:

    return (
        owns_business(user, branch.business)
        or works_at_branch(db, user, branch.id)
    )


def is_staff_at_branch(
    db: Session,
    user: UserModel,
    branch_id: int,
) -> bool:

    return (
        user.role.name == "staff"
        and works_at_branch(
            db,
            user,
            branch_id,
        )
    )


def when(
    booking_date: date,
    booking_time: time,
) -> str:

    return (
        f"{booking_date:%a %d %b %Y} "
        f"at {booking_time:%H:%M}"
    )


def booking_out(
    booking: BookingModel,
) -> BookingSchema:

    data = BookingSchema.model_validate(booking)

    data.customer_name = booking.user.name
    data.customer_phone = booking.user.phone
    data.service_name = booking.service.name
    data.branch_name = booking.branch.name
    data.business_name = booking.business.name

    return data


def check_bookable(
    service: ServiceModel,
):

    business = service.business

    if (
        not service.is_active
        or not service.branch.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This service is not available",
        )

    if (
        business.approval_status != "approved"
        or not business.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This business is not taking bookings",
        )


# ---------------------------------------------------------
# Duration
# ---------------------------------------------------------

def service_duration(
    service: ServiceModel,
) -> int:

    duration = (
        service.duration_minutes
        or DEFAULT_DURATION_MINUTES
    )

    if duration <= 0:
        return DEFAULT_DURATION_MINUTES

    return duration


def booking_start(
    booking_date: date,
    booking_time: time,
) -> datetime:

    return datetime.combine(
        booking_date,
        booking_time,
    )


def booking_end(
    booking_date: date,
    booking_time: time,
    duration_minutes: int,
) -> datetime:

    return (
        booking_start(
            booking_date,
            booking_time,
        )
        + timedelta(
            minutes=duration_minutes
        )
    )


def bookings_overlap(
    start_a: datetime,
    end_a: datetime,
    start_b: datetime,
    end_b: datetime,
) -> bool:

    return (
        start_a < end_b
        and start_b < end_a
    )


# ---------------------------------------------------------
# Operating hours
# ---------------------------------------------------------

def get_operating_hours(
    db: Session,
    branch_id: int,
    booking_date: date,
):

    day = (
        booking_date
        .strftime("%A")
        .lower()
    )

    return (
        db.query(OperatingHourModel)
        .filter(
            OperatingHourModel.branch_id
            == branch_id,
            OperatingHourModel.day_of_week
            == day,
        )
        .first()
    )


def time_is_open(
    hours: OperatingHourModel,
    booking_time: time,
) -> bool:

    if (
        not hours.open_time
        or not hours.close_time
    ):
        return True

    # Normal opening hours:
    # 09:00 -> 17:00
    if hours.open_time < hours.close_time:
        return (
            hours.open_time
            <= booking_time
            < hours.close_time
        )

    # Overnight:
    # 20:00 -> 02:00
    return (
        booking_time >= hours.open_time
        or booking_time < hours.close_time
    )


def booking_fits_operating_hours(
    hours: OperatingHourModel,
    booking_date: date,
    booking_time: time,
    duration_minutes: int,
) -> bool:

    if (
        not hours.open_time
        or not hours.close_time
    ):
        return True

    start = datetime.combine(
        booking_date,
        booking_time,
    )

    end = (
        start
        + timedelta(
            minutes=duration_minutes
        )
    )

    opening = datetime.combine(
        booking_date,
        hours.open_time,
    )

    closing = datetime.combine(
        booking_date,
        hours.close_time,
    )

    # Overnight:
    # 20:00 -> 02:00
    if hours.close_time <= hours.open_time:
        closing += timedelta(days=1)

        if booking_time < hours.close_time:
            opening -= timedelta(days=1)

    return (
        start >= opening
        and end <= closing
    )


# ---------------------------------------------------------
# Existing booking overlap
# ---------------------------------------------------------

def service_has_overlap(
    db: Session,
    service: ServiceModel,
    booking_date: date,
    booking_time: time,
    exclude_id: Optional[int] = None,
) -> bool:

    duration = service_duration(service)

    new_start = booking_start(
        booking_date,
        booking_time,
    )

    new_end = booking_end(
        booking_date,
        booking_time,
        duration,
    )

    query = (
        db.query(BookingModel)
        .filter(
            BookingModel.service_id
            == service.id,
            BookingModel.status.in_(
                OPEN_STATUSES
            ),
        )
    )

    if exclude_id is not None:
        query = query.filter(
            BookingModel.id != exclude_id
        )

    bookings = query.all()

    for existing in bookings:

        existing_duration = service_duration(
            existing.service
        )

        existing_start = booking_start(
            existing.booking_date,
            existing.booking_time,
        )

        existing_end = booking_end(
            existing.booking_date,
            existing.booking_time,
            existing_duration,
        )

        if bookings_overlap(
            new_start,
            new_end,
            existing_start,
            existing_end,
        ):
            return True

    return False


def customer_has_overlap(
    db: Session,
    user_id: int,
    service: ServiceModel,
    booking_date: date,
    booking_time: time,
    exclude_id: Optional[int] = None,
) -> bool:

    duration = service_duration(service)

    new_start = booking_start(
        booking_date,
        booking_time,
    )

    new_end = booking_end(
        booking_date,
        booking_time,
        duration,
    )

    query = (
        db.query(BookingModel)
        .filter(
            BookingModel.user_id
            == user_id,
            BookingModel.status.in_(
                OPEN_STATUSES
            ),
        )
    )

    if exclude_id is not None:
        query = query.filter(
            BookingModel.id != exclude_id
        )

    bookings = query.all()

    for existing in bookings:

        existing_duration = service_duration(
            existing.service
        )

        existing_start = booking_start(
            existing.booking_date,
            existing.booking_time,
        )

        existing_end = booking_end(
            existing.booking_date,
            existing.booking_time,
            existing_duration,
        )

        if bookings_overlap(
            new_start,
            new_end,
            existing_start,
            existing_end,
        ):
            return True

    return False


# ---------------------------------------------------------
# Validate selected slot
# ---------------------------------------------------------

def check_slot(
    db: Session,
    service: ServiceModel,
    booking_date: date,
    booking_time: time,
    exclude_id: Optional[int] = None,
    user_id: Optional[int] = None,
):

    duration = service_duration(service)

    start = booking_start(
        booking_date,
        booking_time,
    )

    # -------------------------------
    # Must be future
    # -------------------------------

    if start <= datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Pick a date and time "
                "in the future"
            ),
        )

    # -------------------------------
    # Opening hours
    # -------------------------------

    hours = get_operating_hours(
        db,
        service.branch_id,
        booking_date,
    )

    day = (
        booking_date
        .strftime("%A")
        .lower()
    )

    if hours:

        if hours.is_closed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The branch is closed "
                    f"on {day.title()}"
                ),
            )

        if (
            hours.open_time
            and hours.close_time
        ):

            if not time_is_open(
                hours,
                booking_time,
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "This time is outside "
                        "branch opening hours"
                    ),
                )

            if not booking_fits_operating_hours(
                hours,
                booking_date,
                booking_time,
                duration,
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"This service takes "
                        f"{duration} minutes and "
                        "would finish after the "
                        "branch closes"
                    ),
                )

    # -------------------------------
    # Service overlap
    # -------------------------------

    if service_has_overlap(
        db,
        service,
        booking_date,
        booking_time,
        exclude_id=exclude_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This time is no longer "
                "available"
            ),
        )

    # -------------------------------
    # Customer overlap
    # -------------------------------

    if (
        user_id is not None
        and customer_has_overlap(
            db,
            user_id,
            service,
            booking_date,
            booking_time,
            exclude_id=exclude_id,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "You already have another "
                "booking during this time"
            ),
        )


# ---------------------------------------------------------
# Available slots
# ---------------------------------------------------------

def build_available_slots(
    db: Session,
    service: ServiceModel,
    booking_date: date,
    user_id: int,
) -> list[str]:

    duration = service_duration(service)

    hours = get_operating_hours(
        db,
        service.branch_id,
        booking_date,
    )

    # We need opening hours to know what slots
    # should actually be displayed.
    if not hours:
        return []

    if hours.is_closed:
        return []

    if (
        not hours.open_time
        or not hours.close_time
    ):
        return []

    opening = datetime.combine(
        booking_date,
        hours.open_time,
    )

    closing = datetime.combine(
        booking_date,
        hours.close_time,
    )

    # Overnight hours:
    # Example 20:00 -> 02:00
    if hours.close_time <= hours.open_time:
        closing += timedelta(days=1)

    slots = []

    current = opening

    while (
        current
        + timedelta(minutes=duration)
        <= closing
    ):

        # Do not show past times.
        if current > datetime.now():

            slot_date = current.date()
            slot_time = current.time()

            service_busy = service_has_overlap(
                db,
                service,
                slot_date,
                slot_time,
            )

            customer_busy = customer_has_overlap(
                db,
                user_id,
                service,
                slot_date,
                slot_time,
            )

            if (
                not service_busy
                and not customer_busy
            ):
                slots.append(
                    current.strftime("%H:%M")
                )

        current += timedelta(
            minutes=duration
        )

    return slots


@router.get(
    "/services/{service_id}/available-slots",
    response_model=AvailableSlotsSchema,
)
def available_slots(
    service_id: int,
    booking_date: date = Query(...),
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):

    service = find_service(
        db,
        service_id,
    )

    check_bookable(service)

    if booking_date < date.today():
        return AvailableSlotsSchema(
            booking_date=booking_date,
            service_id=service.id,
            duration_minutes=service_duration(
                service
            ),
            slots=[],
        )

    slots = build_available_slots(
        db,
        service,
        booking_date,
        user.id,
    )

    return AvailableSlotsSchema(
        booking_date=booking_date,
        service_id=service.id,
        duration_minutes=service_duration(
            service
        ),
        slots=slots,
    )


# ---------------------------------------------------------
# Customer creates booking
# ---------------------------------------------------------

@router.post(
    "/services/{service_id}/bookings",
    response_model=BookingSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    service_id: int,
    data: BookingCreateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):

    service = find_service(
        db,
        service_id,
    )

    check_bookable(service)

    check_slot(
        db,
        service,
        data.booking_date,
        data.booking_time,
        user_id=user.id,
    )

    booking = BookingModel(
        user_id=user.id,
        business_id=service.business_id,
        branch_id=service.branch_id,
        service_id=service.id,
        booking_date=data.booking_date,
        booking_time=data.booking_time,

        # No owner approval.
        status="confirmed",
    )

    db.add(booking)

    notify(
        service.business.owner,
        "booking",
        "New booking",
        (
            f"{user.name} booked "
            f"{service.name} at "
            f"{service.branch.name} on "
            f"{when(
                data.booking_date,
                data.booking_time,
            )}."
        ),
    )

    notify(
        user,
        "booking",
        "Booking confirmed",
        (
            f"Your {service.name} booking "
            f"at {service.branch.name} is "
            f"confirmed for "
            f"{when(
                data.booking_date,
                data.booking_time,
            )}."
        ),
    )

    db.commit()
    db.refresh(booking)

    return booking_out(booking)


# ---------------------------------------------------------
# Customer: my bookings
# ---------------------------------------------------------

@router.get(
    "/bookings/me",
    response_model=list[BookingSchema],
)
def get_my_bookings(
    db: Session = Depends(get_db),
    user: UserModel = Depends(
        require_customer
    ),
):

    bookings = (
        db.query(BookingModel)
        .filter(
            BookingModel.user_id
            == user.id
        )
        .order_by(
            BookingModel.booking_date.desc(),
            BookingModel.booking_time.desc(),
        )
        .all()
    )

    return [
        booking_out(booking)
        for booking in bookings
    ]


# ---------------------------------------------------------
# Owner / staff: branch bookings
# ---------------------------------------------------------

@router.get(
    "/branches/{branch_id}/bookings",
    response_model=list[BookingSchema],
)
def get_branch_bookings(
    branch_id: int,

    status_filter: Optional[
        BookingStatus
    ] = Query(
        default=None,
        alias="status",
    ),

    booking_date: Optional[date] = None,

    db: Session = Depends(get_db),

    user: UserModel = Depends(
        require_owner_or_staff
    ),
):

    branch = find_branch(
        db,
        branch_id,
    )

    if not can_manage_branch(
        db,
        user,
        branch,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You can't see this "
                "branch's bookings"
            ),
        )

    query = (
        db.query(BookingModel)
        .filter(
            BookingModel.branch_id
            == branch.id
        )
    )

    if status_filter:
        query = query.filter(
            BookingModel.status
            == status_filter
        )

    if booking_date:
        query = query.filter(
            BookingModel.booking_date
            == booking_date
        )

    bookings = (
        query
        .order_by(
            BookingModel.booking_date,
            BookingModel.booking_time,
        )
        .all()
    )

    return [
        booking_out(booking)
        for booking in bookings
    ]


# ---------------------------------------------------------
# One booking
# ---------------------------------------------------------

@router.get(
    "/bookings/{booking_id}",
    response_model=BookingSchema,
)
def show_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(
        get_current_user
    ),
):

    booking = find_booking(
        db,
        booking_id,
    )

    if (
        booking.user_id != user.id
        and not can_manage_branch(
            db,
            user,
            booking.branch,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You can't see this booking"
            ),
        )

    return booking_out(booking)


# ---------------------------------------------------------
# Customer reschedule
# ---------------------------------------------------------

def customer_reschedule(
    db: Session,
    booking: BookingModel,
    updates: dict,
):

    if "status" in updates:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Customers can't change "
                "booking status"
            ),
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only confirmed bookings "
                "can be rescheduled"
            ),
        )

    new_date = (
        updates.get("booking_date")
        or booking.booking_date
    )

    new_time = (
        updates.get("booking_time")
        or booking.booking_time
    )

    if (
        new_date == booking.booking_date
        and new_time == booking.booking_time
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "That's the same date "
                "and time"
            ),
        )

    check_bookable(
        booking.service
    )

    check_slot(
        db,
        booking.service,
        new_date,
        new_time,
        exclude_id=booking.id,
        user_id=booking.user_id,
    )

    booking.booking_date = new_date
    booking.booking_time = new_time

    # Still confirmed.
    # No owner approval needed.
    booking.status = "confirmed"

    notify(
        booking.business.owner,
        "booking",
        "Booking rescheduled",
        (
            f"{booking.user.name} moved "
            f"{booking.service.name} to "
            f"{when(
                new_date,
                new_time,
            )}."
        ),
    )

    notify(
        booking.user,
        "booking",
        "Booking rescheduled",
        (
            f"Your {booking.service.name} "
            f"booking is confirmed for "
            f"{when(
                new_date,
                new_time,
            )}."
        ),
    )


# ---------------------------------------------------------
# Staff status update
# ---------------------------------------------------------

def staff_update(
    booking: BookingModel,
    updates: dict,
):

    if set(updates) - {"status"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Staff can only change "
                "booking status"
            ),
        )

    new_status = updates.get("status")

    if new_status not in {
        "completed",
        "no_show",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Staff can mark a booking "
                "as completed or no_show"
            ),
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only confirmed bookings "
                "can be completed or "
                "marked no-show"
            ),
        )

    booking.status = new_status

    title = (
        "Booking completed"
        if new_status == "completed"
        else "Booking marked as no-show"
    )

    notify(
        booking.user,
        "booking",
        title,
        (
            f"{booking.service.name} at "
            f"{booking.branch.name} on "
            f"{when(
                booking.booking_date,
                booking.booking_time,
            )}."
        ),
    )


# ---------------------------------------------------------
# Update booking
# ---------------------------------------------------------

@router.patch(
    "/bookings/{booking_id}",
    response_model=BookingSchema,
)
def update_booking(
    booking_id: int,
    data: BookingUpdateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(
        get_current_user
    ),
):

    booking = find_booking(
        db,
        booking_id,
    )

    updates = data.model_dump(
        exclude_unset=True
    )

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to update",
        )

    # Customer owns booking:
    # reschedule only.
    if booking.user_id == user.id:

        customer_reschedule(
            db,
            booking,
            updates,
        )

    # Staff at this branch:
    # complete or no-show.
    elif is_staff_at_branch(
        db,
        user,
        booking.branch_id,
    ):

        staff_update(
            booking,
            updates,
        )

    # Owner may view bookings,
    # but does not operate appointments.
    elif owns_business(
        user,
        booking.business,
    ):

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Owners can view bookings. "
                "Booking completion and "
                "no-show actions are handled "
                "by branch staff"
            ),
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You can't change this booking"
            ),
        )

    db.commit()
    db.refresh(booking)

    return booking_out(booking)


# ---------------------------------------------------------
# Customer cancel booking
# ---------------------------------------------------------

@router.delete(
    "/bookings/{booking_id}",
)
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(
        require_customer
    ),
):

    booking = find_booking(
        db,
        booking_id,
    )

    if booking.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This isn't your booking"
            ),
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This booking is already "
                "finished"
            ),
        )

    booking.status = "cancelled"

    notify(
        booking.business.owner,
        "booking",
        "Booking cancelled by customer",
        (
            f"{booking.user.name} cancelled "
            f"{booking.service.name} on "
            f"{when(
                booking.booking_date,
                booking.booking_time,
            )}."
        ),
    )

    db.commit()

    return {
        "message": "Booking cancelled"
    }
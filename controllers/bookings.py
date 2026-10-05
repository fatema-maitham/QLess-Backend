# controllers/bookings.py
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies.get_current_user import get_current_user
from dependencies.queue_access import find_branch, owns_business, works_at_branch
from dependencies.roles import require_customer, require_owner_or_staff
from models.booking import BookingModel
from models.branch import BranchModel
from models.operating_hour import OperatingHourModel
from models.service import ServiceModel
from models.user import UserModel
from serializers.booking import BookingCreateSchema, BookingSchema, BookingStatus, BookingUpdateSchema
from services.notifications import notify

router = APIRouter(tags=["Bookings"])

OPEN_STATUSES = ["pending", "confirmed"]

# Owner/staff: which status a booking must have before it can move to the new one
BOOKING_MOVES = {
    "confirmed": {"pending"},
    "completed": {"confirmed"},
    "cancelled": {"pending", "confirmed"},
}

STATUS_TITLES = {
    "confirmed": "Booking confirmed",
    "completed": "Booking completed",
    "cancelled": "Booking cancelled",
}


# ---------- Helpers ----------

def find_service(db: Session, service_id: int) -> ServiceModel:
    service = db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


def find_booking(db: Session, booking_id: int) -> BookingModel:
    booking = db.query(BookingModel).filter(BookingModel.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


def can_manage_branch(db: Session, user: UserModel, branch: BranchModel) -> bool:
    return owns_business(user, branch.business) or works_at_branch(db, user, branch.id)


def when(booking_date: date, booking_time: time) -> str:
    return f"{booking_date:%a %d %b %Y} at {booking_time:%H:%M}"


def booking_out(booking: BookingModel) -> BookingSchema:
    data = BookingSchema.model_validate(booking)
    data.customer_name = booking.user.name
    data.customer_phone = booking.user.phone
    data.service_name = booking.service.name
    data.branch_name = booking.branch.name
    data.business_name = booking.business.name
    return data


def check_bookable(service: ServiceModel):
    business = service.business
    if not service.is_active or not service.branch.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This service is not available")
    if business.approval_status != "approved" or not business.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This business is not taking bookings")


def time_is_open(hours: OperatingHourModel, booking_time: time) -> bool:
    """True if the time is inside the day's hours. Works for hours past midnight too (20:00-02:00)."""
    if hours.open_time < hours.close_time:
        return hours.open_time <= booking_time < hours.close_time
    return booking_time >= hours.open_time or booking_time < hours.close_time


def check_slot(
    db: Session,
    service: ServiceModel,
    booking_date: date,
    booking_time: time,
    exclude_id: Optional[int] = None,
    user_id: Optional[int] = None,
):
    if datetime.combine(booking_date, booking_time) <= datetime.now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick a date and time in the future")

    # Check the branch's operating hours for that day (if the owner set them)
    day = booking_date.strftime("%A").lower()
    hours = (
        db.query(OperatingHourModel)
        .filter(OperatingHourModel.branch_id == service.branch_id, OperatingHourModel.day_of_week == day)
        .first()
    )
    if hours:
        if hours.is_closed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"The branch is closed on {day.title()}")
        if hours.open_time and hours.close_time and not time_is_open(hours, booking_time):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The branch is open {hours.open_time:%H:%M}–{hours.close_time:%H:%M} on {day.title()}",
            )

    # The customer can't have two bookings at the same time (at any place)
    if user_id is not None:
        mine = db.query(BookingModel).filter(
            BookingModel.user_id == user_id,
            BookingModel.booking_date == booking_date,
            BookingModel.booking_time == booking_time,
            BookingModel.status.in_(OPEN_STATUSES),
        )
        if exclude_id is not None:
            mine = mine.filter(BookingModel.id != exclude_id)
        if mine.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have another booking at that time. Pick another time",
            )

    taken = db.query(BookingModel).filter(
        BookingModel.service_id == service.id,
        BookingModel.booking_date == booking_date,
        BookingModel.booking_time == booking_time,
        BookingModel.status.in_(OPEN_STATUSES),
    )
    if exclude_id is not None:
        taken = taken.filter(BookingModel.id != exclude_id)
    if taken.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That time is already booked. Pick another time")


# ---------- Customer: book a service ----------

@router.post("/services/{service_id}/bookings", response_model=BookingSchema, status_code=status.HTTP_201_CREATED)
def create_booking(
    service_id: int,
    data: BookingCreateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    service = find_service(db, service_id)
    check_bookable(service)
    check_slot(db, service, data.booking_date, data.booking_time, user_id=user.id)

    booking = BookingModel(
        user_id=user.id,
        business_id=service.business_id,
        branch_id=service.branch_id,
        service_id=service.id,
        booking_date=data.booking_date,
        booking_time=data.booking_time,
        status="pending",
    )
    db.add(booking)

    notify(
        service.business.owner,
        "booking",
        "New booking request",
        f"{user.name} booked {service.name} at {service.branch.name} on {when(data.booking_date, data.booking_time)}.",
    )

    db.commit()
    db.refresh(booking)
    return booking_out(booking)


# ---------- Customer: my bookings ----------

@router.get("/bookings/me", response_model=list[BookingSchema])
def get_my_bookings(
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    bookings = (
        db.query(BookingModel)
        .filter(BookingModel.user_id == user.id)
        .order_by(BookingModel.booking_date.desc(), BookingModel.booking_time.desc())
        .all()
    )
    return [booking_out(booking) for booking in bookings]


# ---------- Owner/staff: bookings at a branch ----------

@router.get("/branches/{branch_id}/bookings", response_model=list[BookingSchema])
def get_branch_bookings(
    branch_id: int,
    status_filter: Optional[BookingStatus] = Query(default=None, alias="status"),
    booking_date: Optional[date] = None,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_owner_or_staff),
):
    branch = find_branch(db, branch_id)
    if not can_manage_branch(db, user, branch):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't see this branch's bookings")

    query = db.query(BookingModel).filter(BookingModel.branch_id == branch.id)
    if status_filter:
        query = query.filter(BookingModel.status == status_filter)
    if booking_date:
        query = query.filter(BookingModel.booking_date == booking_date)

    bookings = query.order_by(BookingModel.booking_date, BookingModel.booking_time).all()
    return [booking_out(booking) for booking in bookings]


# ---------- One booking ----------

@router.get("/bookings/{booking_id}", response_model=BookingSchema)
def show_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    booking = find_booking(db, booking_id)
    if booking.user_id != user.id and not can_manage_branch(db, user, booking.branch):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't see this booking")
    return booking_out(booking)


def customer_reschedule(db: Session, booking: BookingModel, updates: dict):
    if "status" in updates:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers can't change the status. To cancel, delete the booking",
        )
    if booking.status not in OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This booking is already finished")

    new_date = updates.get("booking_date") or booking.booking_date
    new_time = updates.get("booking_time") or booking.booking_time
    if new_date == booking.booking_date and new_time == booking.booking_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That's the same date and time")

    check_bookable(booking.service)
    check_slot(db, booking.service, new_date, new_time, exclude_id=booking.id, user_id=booking.user_id)

    booking.booking_date = new_date
    booking.booking_time = new_time
    booking.status = "pending"  # the business needs to confirm the new time

    notify(
        booking.business.owner,
        "booking",
        "Booking rescheduled",
        f"{booking.user.name} moved {booking.service.name} to {when(new_date, new_time)}.",
    )


def manager_update(booking: BookingModel, updates: dict):
    if set(updates) - {"status"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owners and staff can only change the status")

    new_status = updates.get("status")
    if new_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Send a status")

    if booking.status not in BOOKING_MOVES[new_status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can't change a {booking.status} booking to {new_status}",
        )

    booking.status = new_status

    notify(
        booking.user,
        "booking",
        STATUS_TITLES[new_status],
        f"{booking.service.name} at {booking.branch.name} on {when(booking.booking_date, booking.booking_time)}.",
    )


@router.patch("/bookings/{booking_id}", response_model=BookingSchema)
def update_booking(
    booking_id: int,
    data: BookingUpdateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    booking = find_booking(db, booking_id)

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")

    if booking.user_id == user.id:
        customer_reschedule(db, booking, updates)
    elif can_manage_branch(db, user, booking.branch):
        manager_update(booking, updates)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't change this booking")

    db.commit()
    db.refresh(booking)
    return booking_out(booking)


# ---------- Customer: cancel ----------

@router.delete("/bookings/{booking_id}")
def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    booking = find_booking(db, booking_id)

    if booking.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This isn't your booking")
    if booking.status not in OPEN_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This booking is already finished")

    booking.status = "cancelled"

    notify(
        booking.business.owner,
        "booking",
        "Booking cancelled by customer",
        f"{booking.user.name} cancelled {booking.service.name} on {when(booking.booking_date, booking.booking_time)}.",
    )

    db.commit()
    return {"message": "Booking cancelled"}
# serializers/booking.py

from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


BookingStatus = Literal[
    "confirmed",
    "completed",
    "cancelled",
    "no_show",
]


class BookingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    business_id: int
    branch_id: int
    service_id: int

    booking_date: date
    booking_time: time
    status: BookingStatus

    created_at: Optional[datetime] = None

    # Filled by the controller
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    service_name: Optional[str] = None
    branch_name: Optional[str] = None
    business_name: Optional[str] = None


class BookingCreateSchema(BaseModel):
    booking_date: date
    booking_time: time


class BookingUpdateSchema(BaseModel):
    # Customer can reschedule.
    booking_date: Optional[date] = None
    booking_time: Optional[time] = None

    # Staff can complete / no-show.
    status: Optional[
        Literal[
            "completed",
            "no_show",
        ]
    ] = None


class AvailableSlotsSchema(BaseModel):
    booking_date: date
    service_id: int
    duration_minutes: int
    slots: list[str]
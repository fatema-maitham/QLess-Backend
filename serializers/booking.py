# serializers/booking.py
from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

BookingStatus = Literal["pending", "confirmed", "completed", "cancelled"]


class BookingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    business_id: int
    branch_id: int
    service_id: int
    booking_date: date
    booking_time: time
    status: str
    created_at: Optional[datetime] = None

    # Filled in by the controller
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    service_name: Optional[str] = None
    branch_name: Optional[str] = None
    business_name: Optional[str] = None


class BookingCreateSchema(BaseModel):
    booking_date: date  # "2026-10-05"
    booking_time: time  # "10:30"


class BookingUpdateSchema(BaseModel):
    # Customer: booking_date / booking_time (reschedule)
    # Owner/staff: status
    booking_date: Optional[date] = None
    booking_time: Optional[time] = None
    status: Optional[Literal["confirmed", "completed", "cancelled"]] = None
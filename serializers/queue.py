# serializers/queue.py
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

QueueStatus = Literal["open", "paused", "closed"]


class QueueSchema(BaseModel):
    """What the API sends back about a queue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    branch_id: int
    service_id: Optional[int] = None
    name: str
    status: str
    current_number: int
    max_capacity: Optional[int] = None
    average_service_minutes: int
    no_show_grace_minutes: int
    created_at: Optional[datetime] = None
    waiting_count: int = 0  # filled in by the controller


class QueueCreateSchema(BaseModel):
    name: str = Field(min_length=1)
    service_id: Optional[int] = None
    max_capacity: Optional[int] = Field(default=None, ge=1)
    average_service_minutes: int = Field(default=10, ge=1)
    no_show_grace_minutes: int = Field(default=5, ge=0)


class QueueUpdateSchema(BaseModel):
    # Owners can send any of these. Staff can only send "status".
    name: Optional[str] = Field(default=None, min_length=1)
    service_id: Optional[int] = None
    max_capacity: Optional[int] = Field(default=None, ge=1)
    average_service_minutes: Optional[int] = Field(default=None, ge=1)
    no_show_grace_minutes: Optional[int] = Field(default=None, ge=0)
    status: Optional[QueueStatus] = None


class CalledEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    queue_number: int
    status: str
    called_at: Optional[datetime] = None


class CallNextResponseSchema(BaseModel):
    message: str
    queue: QueueSchema
    entry: CalledEntrySchema


class QueueAnalyticsSchema(BaseModel):
    queue_id: int
    total_entries: int
    waiting: int
    called: int
    checked_in: int
    completed: int
    cancelled: int
    no_show: int
    no_show_rate: float  # percent of finished entries that were no-shows
    average_wait_minutes: Optional[float] = None  # joined -> called
    average_service_minutes: Optional[float] = None  # checked in -> completed
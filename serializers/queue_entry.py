# serializers/queue_entry.py
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

EntryStatus = Literal["waiting", "called", "checked_in", "completed", "cancelled", "no_show"]


class QueueEntrySchema(BaseModel):
    """One ticket in a queue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    queue_id: int
    user_id: int
    queue_number: int
    status: str
    on_the_way: bool
    joined_at: Optional[datetime] = None
    called_at: Optional[datetime] = None
    checked_in_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    no_show_at: Optional[datetime] = None
    counter_number: Optional[int] = None  # the counter that called this ticket

    # Filled in by the controller
    customer_name: Optional[str] = None
    queue_name: Optional[str] = None
    queue_status: Optional[str] = None
    current_number: Optional[int] = None
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None
    business_name: Optional[str] = None
    position: Optional[int] = None
    people_ahead: Optional[int] = None
    estimated_wait_minutes: Optional[int] = None
    recommended_return_time: Optional[datetime] = None


class MyQueueEntriesSchema(BaseModel):
    active: list[QueueEntrySchema]
    history: list[QueueEntrySchema]


class QueueEntryUpdateSchema(BaseModel):
    # Customer: on_the_way, or status "checked_in"
    # Owner/staff: status "checked_in", "completed" or "no_show"
    on_the_way: Optional[bool] = None
    status: Optional[Literal["checked_in", "completed", "no_show"]] = None
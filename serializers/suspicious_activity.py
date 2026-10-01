# serializers/suspicious_activity.py
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

ActivityStatus = Literal["open", "reviewed", "dismissed"]
Severity = Literal["low", "medium", "high"]


class SuspiciousActivitySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    queue_id: Optional[int] = None
    activity_type: str
    description: Optional[str] = None
    severity: str
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    # Filled in by the controller
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_no_show_count: Optional[int] = None
    user_restricted_until: Optional[datetime] = None
    queue_name: Optional[str] = None
    reviewer_name: Optional[str] = None


class SuspiciousActivityUpdateSchema(BaseModel):
    status: ActivityStatus
    note: Optional[str] = None  # saved in the audit log
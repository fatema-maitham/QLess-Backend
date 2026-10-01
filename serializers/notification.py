# serializers/notification.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NotificationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    message: Optional[str] = None
    is_read: bool
    created_at: Optional[datetime] = None


class NotificationListSchema(BaseModel):
    unread_count: int
    notifications: list[NotificationSchema]


class NotificationUpdateSchema(BaseModel):
    is_read: bool
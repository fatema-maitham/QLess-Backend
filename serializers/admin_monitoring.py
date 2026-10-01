# serializers/admin_monitoring.py
from typing import Optional

from serializers.queue import QueueSchema


class AdminQueueSchema(QueueSchema):
    """A queue plus where it belongs, for the admin Queues page."""

    business_name: Optional[str] = None
    branch_name: Optional[str] = None
    service_name: Optional[str] = None
    called_count: int = 0
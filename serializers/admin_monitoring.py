from typing import Optional

from serializers.queue import QueueSchema


class AdminQueueSchema(QueueSchema):
    """Queue data used by the Admin Live Queues page."""

    business_name: Optional[str] = None
    business_image: Optional[str] = None

    branch_name: Optional[str] = None
    service_name: Optional[str] = None

    called_count: int = 0
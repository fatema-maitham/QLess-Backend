from .base import Base, BaseModel

# Import every model module so SQLAlchemy and Alembic can see all tables.
from . import (
    role,
    user,
    category,
    business,
    branch,
    service,
    operating_hour,
    staff,
    announcement,
    queue,
    queue_entry,
    booking,
    notification,
    review,
    favorite,
    suspicious_activity,
    audit_log,
)

__all__ = ["Base", "BaseModel"]

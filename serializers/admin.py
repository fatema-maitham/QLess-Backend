# serializers/admin.py
from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict

from serializers.branch import BranchSchema
from serializers.business import BusinessSchema


# ----- small "brief" versions shown inside other objects -----

class AdminUserBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class AdminBusinessBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# ----- responses -----

class AdminBusinessSchema(BusinessSchema):
    """A business plus who owns it."""

    owner: AdminUserBriefSchema


class AdminBranchSchema(BranchSchema):
    """A branch plus which business it belongs to."""

    business: AdminBusinessBriefSchema


class AuditLogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: Optional[int] = None
    admin: Optional[AdminUserBriefSchema] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class DashboardSchema(BaseModel):
    users_total: int
    users_by_role: Dict[str, int]
    active_users: int
    restricted_users: int
    businesses_total: int
    businesses_by_status: Dict[str, int]
    branches_total: int
    active_branches: int
    queues_total: int
    open_queues: int
    people_waiting: int
    bookings_total: int
    reviews_total: int
    open_suspicious_activities: int


# ----- request bodies -----

class AdminUserUpdateSchema(BaseModel):
    """Send is_active to activate/deactivate. Send restricted_until: null to lift a restriction."""

    is_active: Optional[bool] = None
    restricted_until: Optional[datetime] = None


class AdminBusinessUpdateSchema(BaseModel):
    """Approve or reject a pending business, or activate/deactivate any business."""

    approval_status: Optional[Literal["approved", "rejected"]] = None
    rejection_reason: Optional[str] = None
    is_active: Optional[bool] = None


class AdminBranchUpdateSchema(BaseModel):
    is_active: bool
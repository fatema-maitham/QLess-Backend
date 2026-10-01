from typing import Optional

from sqlalchemy.orm import Session

from models.audit_log import AuditLogModel
from models.user import UserModel


def log_admin_action(
    db: Session,
    admin: UserModel,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    description: Optional[str] = None,
):
    """Save one admin action. The caller does db.commit() afterwards.

    Example:
        log_admin_action(db, admin, "approve_business", "business", business.id, "Approved Coffee Corner")
    """
    db.add(
        AuditLogModel(
            admin_id=admin.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
        )
    )
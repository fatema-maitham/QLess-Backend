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


def paused_by_admin(db: Session, entity_type: str, entity_id: int) -> bool:
    """True if the last admin action on this branch/business was a deactivate.
    Used so an owner can't turn back on something an admin paused."""
    last = (
        db.query(AuditLogModel)
        .filter(
            AuditLogModel.entity_type == entity_type,
            AuditLogModel.entity_id == entity_id,
            AuditLogModel.action.in_([f"activate_{entity_type}", f"deactivate_{entity_type}"]),
        )
        .order_by(AuditLogModel.created_at.desc(), AuditLogModel.id.desc())
        .first()
    )
    return last is not None and last.action == f"deactivate_{entity_type}"
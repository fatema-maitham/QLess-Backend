# controllers/admin.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from dependencies.roles import require_admin
from models.audit_log import AuditLogModel
from models.booking import BookingModel
from models.branch import BranchModel
from models.business import BusinessModel
from models.notification import NotificationModel
from models.queue import QueueModel
from models.queue_entry import QueueEntryModel
from models.review import ReviewModel
from models.role import RoleModel
from models.suspicious_activity import SuspiciousActivityModel
from models.user import UserModel
from serializers.admin import (
    AdminBranchSchema,
    AdminBranchUpdateSchema,
    AdminBusinessSchema,
    AdminBusinessUpdateSchema,
    AdminUserUpdateSchema,
    AuditLogSchema,
    DashboardSchema,
)
from serializers.user import UserSchema
from services.audit_log import log_admin_action

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------- helpers ----------

def count(db: Session, column, *filters) -> int:
    return db.query(func.count(column)).filter(*filters).scalar() or 0


def notify_owner(db: Session, business: BusinessModel, title: str, message: str):
    """Tell the business owner what the admin did."""
    db.add(
        NotificationModel(
            user_id=business.owner_id,
            type="business_status",
            title=title,
            message=message,
        )
    )


def get_user_or_404(db: Session, user_id: int) -> UserModel:
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# ---------- dashboard ----------

@router.get("/dashboard", response_model=DashboardSchema)
def dashboard(
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    users_by_role = dict(
        db.query(RoleModel.name, func.count(UserModel.id))
        .outerjoin(UserModel, UserModel.role_id == RoleModel.id)
        .group_by(RoleModel.name)
        .all()
    )

    businesses_by_status = {"draft": 0, "pending": 0, "approved": 0, "rejected": 0}
    for status_name, total in (
        db.query(BusinessModel.approval_status, func.count(BusinessModel.id))
        .group_by(BusinessModel.approval_status)
        .all()
    ):
        businesses_by_status[status_name] = total

    return {
        "users_total": count(db, UserModel.id),
        "users_by_role": users_by_role,
        "active_users": count(db, UserModel.id, UserModel.is_active.is_(True)),
        "restricted_users": count(db, UserModel.id, UserModel.restricted_until > func.now()),
        "businesses_total": count(db, BusinessModel.id),
        "businesses_by_status": businesses_by_status,
        "branches_total": count(db, BranchModel.id),
        "active_branches": count(db, BranchModel.id, BranchModel.is_active.is_(True)),
        "queues_total": count(db, QueueModel.id),
        "open_queues": count(db, QueueModel.id, QueueModel.status == "open"),
        "people_waiting": count(db, QueueEntryModel.id, QueueEntryModel.status == "waiting"),
        "bookings_total": count(db, BookingModel.id),
        "reviews_total": count(db, ReviewModel.id),
        "open_suspicious_activities": count(
            db, SuspiciousActivityModel.id, SuspiciousActivityModel.status == "open"
        ),
    }


# ---------- users ----------

@router.get("/users", response_model=List[UserSchema])
def get_users(
    role: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    query = db.query(UserModel)

    if role:
        query = query.join(UserModel.role).filter(RoleModel.name == role)
    if is_active is not None:
        query = query.filter(UserModel.is_active.is_(is_active))
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(UserModel.name.ilike(term), UserModel.email.ilike(term)))

    return query.order_by(UserModel.created_at.desc()).all()


@router.patch("/users/{user_id}", response_model=UserSchema)
def update_user(
    user_id: int,
    data: AdminUserUpdateSchema,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    user = get_user_or_404(db, user_id)
    changes = data.model_dump(exclude_unset=True)

    new_active = changes.get("is_active")
    if new_active is not None and new_active != user.is_active:
        if user.id == admin.id and new_active is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't deactivate yourself")
        user.is_active = new_active
        action = "activate_user" if new_active else "deactivate_user"
        log_admin_action(db, admin, action, "user", user.id, f"{action.replace('_', ' ').capitalize()}: {user.email}")

    if "restricted_until" in changes:
        user.restricted_until = changes["restricted_until"]
        if changes["restricted_until"] is None:
            log_admin_action(db, admin, "lift_restriction", "user", user.id, f"Lifted restriction for {user.email}")
        else:
            log_admin_action(
                db, admin, "set_restriction", "user", user.id,
                f"Restricted {user.email} until {changes['restricted_until']}",
            )

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    user = get_user_or_404(db, user_id)

    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You can't delete yourself")
    if user.role.name == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admin accounts can't be deleted here")

    log_admin_action(db, admin, "delete_user", "user", user.id, f"Deleted user {user.email}")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


# ---------- businesses ----------

@router.get("/businesses", response_model=List[AdminBusinessSchema])
def get_businesses(
    approval_status: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    query = db.query(BusinessModel)

    if approval_status:
        query = query.filter(BusinessModel.approval_status == approval_status)
    if is_active is not None:
        query = query.filter(BusinessModel.is_active.is_(is_active))
    if search and search.strip():
        query = query.filter(BusinessModel.name.ilike(f"%{search.strip()}%"))

    return query.order_by(BusinessModel.created_at.desc()).all()


@router.patch("/businesses/{business_id}", response_model=AdminBusinessSchema)
def update_business_status(
    business_id: int,
    data: AdminBusinessUpdateSchema,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    business = db.query(BusinessModel).filter(BusinessModel.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")

    changes = data.model_dump(exclude_unset=True)

    # Approve / reject
    new_status = changes.get("approval_status")
    if new_status:
        if business.approval_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only pending businesses can be approved or rejected (current status: {business.approval_status})",
            )

        if new_status == "rejected":
            reason = (changes.get("rejection_reason") or "").strip()
            if not reason:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A rejection reason is required")
            business.approval_status = "rejected"
            business.rejection_reason = reason
            notify_owner(db, business, "Business rejected", f'"{business.name}" was rejected: {reason}')
            log_admin_action(db, admin, "reject_business", "business", business.id, f"Rejected {business.name}: {reason}")
        else:
            business.approval_status = "approved"
            business.rejection_reason = None
            notify_owner(db, business, "Business approved", f'"{business.name}" is approved and now visible to customers.')
            log_admin_action(db, admin, "approve_business", "business", business.id, f"Approved {business.name}")

    # Activate / deactivate
    new_active = changes.get("is_active")
    if new_active is not None and new_active != business.is_active:
        business.is_active = new_active
        if new_active:
            notify_owner(db, business, "Business reactivated", f'"{business.name}" was reactivated by an admin.')
            log_admin_action(db, admin, "activate_business", "business", business.id, f"Activated {business.name}")
        else:
            notify_owner(db, business, "Business deactivated", f'"{business.name}" was deactivated by an admin.')
            log_admin_action(db, admin, "deactivate_business", "business", business.id, f"Deactivated {business.name}")

    db.commit()
    db.refresh(business)
    return business


# ---------- branches ----------

@router.get("/branches", response_model=List[AdminBranchSchema])
def get_branches(
    business_id: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    query = db.query(BranchModel)

    if business_id is not None:
        query = query.filter(BranchModel.business_id == business_id)
    if is_active is not None:
        query = query.filter(BranchModel.is_active.is_(is_active))

    return query.order_by(BranchModel.created_at.desc()).all()


@router.patch("/branches/{branch_id}", response_model=AdminBranchSchema)
def update_branch_status(
    branch_id: int,
    data: AdminBranchUpdateSchema,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    branch = db.query(BranchModel).filter(BranchModel.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    if data.is_active != branch.is_active:
        branch.is_active = data.is_active
        action = "activate_branch" if data.is_active else "deactivate_branch"
        log_admin_action(
            db, admin, action, "branch", branch.id,
            f"{'Activated' if data.is_active else 'Deactivated'} {branch.name} ({branch.business.name})",
        )

    db.commit()
    db.refresh(branch)
    return branch


# ---------- audit logs ----------

@router.get("/audit-logs", response_model=List[AuditLogSchema])
def get_audit_logs(
    entity_type: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    query = db.query(AuditLogModel)

    if entity_type:
        query = query.filter(AuditLogModel.entity_type == entity_type)
    if action:
        query = query.filter(AuditLogModel.action == action)

    return query.order_by(AuditLogModel.created_at.desc(), AuditLogModel.id.desc()).limit(limit).all()
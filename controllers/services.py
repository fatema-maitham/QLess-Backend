from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from controllers.branches import can_manage, get_owned_branch, is_public_business
from database import get_db
from dependencies.get_optional_user import get_optional_user
from dependencies.roles import require_owner
from models.branch import BranchModel
from models.service import ServiceModel
from models.user import UserModel
from serializers.service import ServiceCreateSchema, ServiceSchema, ServiceUpdateSchema

router = APIRouter(tags=["Services"])


# ---------- helpers ----------

def is_public_branch(branch: BranchModel) -> bool:
    return branch.is_active and is_public_business(branch.business)


def get_owned_service(service_id: int, db: Session, user: UserModel) -> ServiceModel:
    """Find a service and make sure the logged-in owner owns its business."""
    service = db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    if service.business.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your service")
    return service


# ---------- routes ----------

@router.get("/branches/{branch_id}/services", response_model=List[ServiceSchema])
def get_services(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
):
    branch = db.query(BranchModel).filter(BranchModel.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    manager = can_manage(current_user, branch.business)

    # The public only sees services of public branches
    if not manager and not is_public_branch(branch):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    query = db.query(ServiceModel).filter(ServiceModel.branch_id == branch_id)

    # The owner and admin also see deactivated services; the public doesn't
    if not manager:
        query = query.filter(ServiceModel.is_active.is_(True))

    return query.order_by(ServiceModel.name).all()


@router.post(
    "/branches/{branch_id}/services",
    response_model=ServiceSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_service(
    branch_id: int,
    data: ServiceCreateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    branch = get_owned_branch(branch_id, db, current_user)

    service = ServiceModel(**data.model_dump(), branch_id=branch.id, business_id=branch.business_id)
    service.name = service.name.strip()

    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/services/{service_id}", response_model=ServiceSchema)
def show_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
):
    service = db.query(ServiceModel).filter(ServiceModel.id == service_id).first()
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    is_public = service.is_active and is_public_branch(service.branch)

    if not is_public and not can_manage(current_user, service.business):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    return service


@router.patch("/services/{service_id}", response_model=ServiceSchema)
def update_service(
    service_id: int,
    data: ServiceUpdateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    service = get_owned_service(service_id, db, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "name":
            if value is None:
                continue  # name can't be empty
            value = value.strip()
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return service


@router.delete("/services/{service_id}")
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """Deactivate (not a real delete), so queues and bookings stay safe."""
    service = get_owned_service(service_id, db, current_user)
    service.is_active = False
    db.commit()
    return {"message": "Service deactivated"}
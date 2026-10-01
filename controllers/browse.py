# controllers/browse.py
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from database import get_db
from models.business import BusinessModel
from models.service import ServiceModel
from serializers.browse import BusinessCardSchema

router = APIRouter(prefix="/businesses", tags=["Browse"])


@router.get("", response_model=list[BusinessCardSchema])
def get_businesses(
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    # Public list: only approved and active businesses
    query = db.query(BusinessModel).filter(
        BusinessModel.approval_status == "approved",
        BusinessModel.is_active.is_(True),
    )

    if category_id is not None:
        query = query.filter(BusinessModel.category_id == category_id)

    # Search by business name, description, or the name of one of its services
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                BusinessModel.name.ilike(term),
                BusinessModel.description.ilike(term),
                BusinessModel.services.any(
                    and_(ServiceModel.name.ilike(term), ServiceModel.is_active.is_(True))
                ),
            )
        )

    return query.order_by(BusinessModel.name).all()
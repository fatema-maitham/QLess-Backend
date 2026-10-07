from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from controllers.reviews import review_out
from database import get_db
from dependencies.roles import require_admin
from models.queue import QueueModel
from models.queue_entry import QueueEntryModel
from models.review import ReviewModel
from models.user import UserModel
from serializers.admin_monitoring import AdminQueueSchema
from serializers.queue import QueueStatus
from serializers.review import ReviewSchema


router = APIRouter(
    prefix="/admin",
    tags=["Admin: Monitoring"],
)


def count_by_status(
    db: Session,
    status_name: str,
) -> dict[int, int]:
    """Return {queue_id: number of entries with this status}."""

    rows = (
        db.query(
            QueueEntryModel.queue_id,
            func.count(QueueEntryModel.id),
        )
        .filter(
            QueueEntryModel.status == status_name
        )
        .group_by(QueueEntryModel.queue_id)
        .all()
    )

    return dict(rows)


@router.get(
    "/queues",
    response_model=list[AdminQueueSchema],
)
def get_queues(
    status_filter: Optional[QueueStatus] = Query(
        default=None,
        alias="status",
    ),
    business_id: Optional[int] = None,
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    query = db.query(QueueModel)

    if status_filter:
        query = query.filter(
            QueueModel.status == status_filter
        )

    if business_id is not None:
        query = query.filter(
            QueueModel.business_id == business_id
        )

    queues = (
        query
        .order_by(
            QueueModel.business_id,
            QueueModel.branch_id,
            QueueModel.name,
        )
        .all()
    )

    waiting = count_by_status(db, "waiting")
    called = count_by_status(db, "called")

    result = []

    for queue in queues:
        data = AdminQueueSchema.model_validate(queue)

        data.waiting_count = waiting.get(
            queue.id,
            0,
        )

        data.called_count = called.get(
            queue.id,
            0,
        )

        data.business_name = queue.business.name
        data.business_image = queue.business.image

        data.branch_name = queue.branch.name

        data.service_name = (
            queue.service.name
            if queue.service
            else None
        )

        result.append(data)

    return result


@router.get(
    "/reviews",
    response_model=list[ReviewSchema],
)
def get_reviews(
    business_id: Optional[int] = None,
    rating: Optional[int] = Query(
        default=None,
        ge=1,
        le=5,
    ),
    db: Session = Depends(get_db),
    admin: UserModel = Depends(require_admin),
):
    query = db.query(ReviewModel)

    if business_id is not None:
        query = query.filter(
            ReviewModel.business_id == business_id
        )

    if rating is not None:
        query = query.filter(
            ReviewModel.rating == rating
        )

    reviews = (
        query
        .order_by(
            ReviewModel.created_at.desc()
        )
        .all()
    )

    return [
        review_out(review)
        for review in reviews
    ]
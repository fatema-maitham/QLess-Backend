# controllers/reviews.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from dependencies.get_current_user import get_current_user
from dependencies.roles import require_customer
from models.audit_log import AuditLogModel
from models.booking import BookingModel
from models.business import BusinessModel
from models.queue import QueueModel
from models.queue_entry import QueueEntryModel
from models.review import ReviewModel
from models.user import UserModel
from serializers.review import BusinessReviewsSchema, ReviewCreateSchema, ReviewSchema, ReviewUpdateSchema
from services.notifications import notify

router = APIRouter(tags=["Reviews"])


# ---------- Helpers ----------

def find_business(db: Session, business_id: int) -> BusinessModel:
    business = db.query(BusinessModel).filter(BusinessModel.id == business_id).first()
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return business


def find_review(db: Session, review_id: int) -> ReviewModel:
    review = db.query(ReviewModel).filter(ReviewModel.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review


def review_out(review: ReviewModel) -> ReviewSchema:
    data = ReviewSchema.model_validate(review)
    data.author_name = review.user.name
    data.business_name = review.business.name
    return data


def has_completed_visit(db: Session, user_id: int, business_id: int) -> bool:
    """True if the user finished a queue ticket or a booking at this business."""
    finished_ticket = (
        db.query(QueueEntryModel.id)
        .join(QueueModel, QueueEntryModel.queue_id == QueueModel.id)
        .filter(
            QueueEntryModel.user_id == user_id,
            QueueEntryModel.status == "completed",
            QueueModel.business_id == business_id,
        )
        .first()
    )
    if finished_ticket:
        return True

    finished_booking = (
        db.query(BookingModel.id)
        .filter(
            BookingModel.user_id == user_id,
            BookingModel.business_id == business_id,
            BookingModel.status == "completed",
        )
        .first()
    )
    return finished_booking is not None


# ---------- Public: reviews for a business ----------

@router.get("/businesses/{business_id}/reviews", response_model=BusinessReviewsSchema)
def get_reviews(business_id: int, db: Session = Depends(get_db)):
    find_business(db, business_id)

    reviews = (
        db.query(ReviewModel)
        .filter(ReviewModel.business_id == business_id)
        .order_by(ReviewModel.created_at.desc())
        .all()
    )
    average = db.query(func.avg(ReviewModel.rating)).filter(ReviewModel.business_id == business_id).scalar()

    return {
        "average_rating": round(float(average), 1) if average is not None else None,
        "review_count": len(reviews),
        "reviews": [review_out(review) for review in reviews],
    }


# ---------- Customer: write a review ----------

@router.post("/businesses/{business_id}/reviews", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
def create_review(
    business_id: int,
    data: ReviewCreateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    business = find_business(db, business_id)

    if business.approval_status != "approved" or not business.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This business can't be reviewed")

    if not has_completed_visit(db, user.id, business.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can review a business after a completed visit or booking",
        )

    already = (
        db.query(ReviewModel)
        .filter(ReviewModel.user_id == user.id, ReviewModel.business_id == business.id)
        .first()
    )
    if already:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already reviewed this business. Edit your review instead",
        )

    comment = data.comment.strip() if data.comment else None
    review = ReviewModel(user_id=user.id, business_id=business.id, rating=data.rating, comment=comment)
    db.add(review)

    notify(business.owner, "review", "New review", f"{user.name} rated {business.name} {data.rating}/5.")

    db.commit()
    db.refresh(review)
    return review_out(review)


# ---------- Author: edit ----------

@router.patch("/reviews/{review_id}", response_model=ReviewSchema)
def update_review(
    review_id: int,
    data: ReviewUpdateSchema,
    db: Session = Depends(get_db),
    user: UserModel = Depends(require_customer),
):
    review = find_review(db, review_id)

    if review.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own review")

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")

    if "rating" in updates and updates["rating"] is not None:
        review.rating = updates["rating"]
    if "comment" in updates:
        review.comment = updates["comment"].strip() if updates["comment"] else None

    db.commit()
    db.refresh(review)
    return review_out(review)


# ---------- Author or admin: delete ----------

@router.delete("/reviews/{review_id}")
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    review = find_review(db, review_id)

    is_author = review.user_id == user.id
    is_admin = user.role.name == "admin"

    if not is_author and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can't delete this review")

    if is_admin and not is_author:
        db.add(
            AuditLogModel(
                admin_id=user.id,
                action="remove_review",
                entity_type="review",
                entity_id=review.id,
                description=(
                    f"Removed {review.user.email}'s {review.rating}/5 review of {review.business.name}"
                ),
            )
        )
        notify(
            review.user,
            "review_removed",
            "Your review was removed",
            f"Your review of {review.business.name} was removed by an admin.",
        )

    db.delete(review)
    db.commit()
    return {"message": "Review deleted"}
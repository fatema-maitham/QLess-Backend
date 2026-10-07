# serializers/review.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ReviewSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    business_id: int
    rating: int
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Filled in by the controller
    author_name: Optional[str] = None
    author_profile_image: Optional[str] = None
    business_name: Optional[str] = None


class BusinessReviewsSchema(BaseModel):
    average_rating: Optional[float] = None
    review_count: int
    reviews: list[ReviewSchema]


class ReviewCreateSchema(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)


class ReviewUpdateSchema(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)
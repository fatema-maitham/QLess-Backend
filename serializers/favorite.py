# serializers/favorite.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from serializers.browse import BusinessCardSchema


class FavoriteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    created_at: Optional[datetime] = None
    business: BusinessCardSchema


class FavoriteCreateSchema(BaseModel):
    business_id: int
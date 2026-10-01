# serializers/browse.py
from typing import Optional

from pydantic import BaseModel, ConfigDict

from serializers.category import CategorySchema


class BusinessCardSchema(BaseModel):
    """One business on the public Browse page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    category: Optional[CategorySchema] = None
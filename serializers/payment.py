# serializers/payment.py
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PlanSchema(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    days: int
    description: str


class PaymentCreateSchema(BaseModel):
    """Card details from the checkout form. Only the last 4 digits are ever saved."""

    plan: Literal["monthly", "yearly"]
    card_holder: str = Field(min_length=2, max_length=80)
    card_number: str = Field(min_length=12, max_length=23)
    exp_month: int
    exp_year: int
    cvc: str = Field(min_length=3, max_length=4)


class PaymentSchema(BaseModel):
    """What the API sends back about a payment (a receipt)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    plan: str
    amount: float
    currency: str
    status: str
    failure_reason: Optional[str] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_holder: Optional[str] = None
    reference: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SubscriptionSchema(BaseModel):
    """The owner's plan right now."""

    business_id: int
    is_paid: bool
    plan: Optional[str] = None
    paid_until: Optional[datetime] = None
    days_left: int
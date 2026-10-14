# controllers/payments.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from controllers.businesses import get_owned_business
from database import get_db
from dependencies.roles import require_owner
from models.business import utc_now
from models.notification import NotificationModel
from models.payment import PaymentModel
from models.user import UserModel
from serializers.payment import PaymentCreateSchema, PaymentSchema, PlanSchema, SubscriptionSchema
from services.payments import (
    CURRENCY,
    PLANS,
    charge_card,
    check_card,
    get_plan,
    new_reference,
    next_period,
)

router = APIRouter(tags=["Payments"])


@router.get("/payments/plans", response_model=List[PlanSchema])
def get_plans():
    """The plans an owner can pay for. Public, so the landing page can show prices too."""
    return [{**plan, "currency": CURRENCY} for plan in PLANS.values()]


@router.get("/businesses/{business_id}/subscription", response_model=SubscriptionSchema)
def get_subscription(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    business = get_owned_business(business_id, db, current_user)
    until = business.paid_until
    days_left = max(0, (until - utc_now()).days) if until and business.is_paid else 0

    return {
        "business_id": business.id,
        "is_paid": business.is_paid,
        "plan": business.current_plan,
        "paid_until": until,
        "days_left": days_left,
    }


@router.get("/businesses/{business_id}/payments", response_model=List[PaymentSchema])
def get_payments(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """The owner's payment history (receipts), newest first."""
    business = get_owned_business(business_id, db, current_user)
    return (
        db.query(PaymentModel)
        .filter(PaymentModel.business_id == business.id)
        .order_by(PaymentModel.created_at.desc(), PaymentModel.id.desc())
        .all()
    )


@router.post(
    "/businesses/{business_id}/payments",
    response_model=PaymentSchema,
    status_code=status.HTTP_201_CREATED,
)
def pay(
    business_id: int,
    data: PaymentCreateSchema,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_owner),
):
    """Pay for a plan. If the business is a draft (or was rejected), it is sent for approval."""
    business = get_owned_business(business_id, db, current_user)
    plan = get_plan(data.plan)
    now = utc_now()

    card = check_card(data.card_number, data.exp_month, data.exp_year, data.cvc, now)

    payment = PaymentModel(
        business_id=business.id,
        owner_id=current_user.id,
        plan=plan["id"],
        amount=plan["price"],
        currency=CURRENCY,
        card_brand=card["brand"],
        card_last4=card["last4"],
        card_holder=data.card_holder.strip(),
        reference=new_reference(),
    )

    declined = charge_card(card["number"], plan["price"])
    if declined:
        # Keep a record of the failed try, then tell the owner
        payment.status = "failed"
        payment.failure_reason = declined
        db.add(payment)
        db.commit()
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=declined)

    payment.status = "paid"
    payment.period_start, payment.period_end = next_period(business.paid_until, plan["days"], now)
    db.add(payment)

    # Paying sends a new (or rejected) business to the admin for approval
    if business.approval_status in ("draft", "rejected"):
        business.approval_status = "pending"
        business.rejection_reason = None

    db.add(
        NotificationModel(
            user_id=current_user.id,
            type="payment",
            title="Payment received",
            message=(
                f'We received {plan["price"]:.3f} {CURRENCY} for the {plan["name"].lower()} plan '
                f'of "{business.name}". Receipt {payment.reference}.'
            ),
        )
    )

    db.commit()
    db.refresh(payment)
    return payment
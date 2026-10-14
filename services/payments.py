# services/payments.py
"""Plans and card checks for owner payments.

This is a demo checkout: no real money moves. Any card number works as long as the
details look complete (number length, expiry date in the future, CVC), then the payment is saved.
To go live later, swap charge_card() for a real gateway (Tap, BenefitPay, Stripe...).
"""
import re
import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status

# Prices are in Bahraini Dinar
PLANS = {
    "monthly": {
        "id": "monthly",
        "name": "Monthly",
        "price": Decimal("15.000"),
        "days": 30,
        "description": "Pay month by month. Cancel any time.",
    },
    "yearly": {
        "id": "yearly",
        "name": "Yearly",
        "price": Decimal("150.000"),
        "days": 365,
        "description": "Two months free compared to monthly.",
    },
}

CURRENCY = "BHD"

def get_plan(plan_id: str) -> dict:
    plan = PLANS.get(plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a valid plan")
    return plan


def clean_number(card_number: str) -> str:
    """Remove spaces and dashes from the card number."""
    return re.sub(r"[\s-]", "", card_number or "")


def card_brand(number: str) -> Optional[str]:
    """Guess the brand from the first digits, just for display. Unknown brands are fine."""
    if number.startswith("4"):
        return "visa"
    if number[:2] in ("34", "37"):
        return "amex"
    if 51 <= int(number[:2]) <= 55 or 2221 <= int(number[:4]) <= 2720:
        return "mastercard"
    return None


def bad_card(message: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def check_card(card_number: str, exp_month: int, exp_year: int, cvc: str, now: datetime) -> dict:
    """Check the card details. Returns {"brand", "last4", "number"} or raises a 400."""
    number = clean_number(card_number)

    if not number.isdigit() or len(number) != 16:
        bad_card("Card number should be 16 digits")

    brand = card_brand(number)

    if not 1 <= exp_month <= 12:
        bad_card("Expiry month should be between 1 and 12")

    # Accept 2-digit years like 28 → 2028
    if exp_year < 100:
        exp_year += 2000
    if (exp_year, exp_month) < (now.year, now.month):
        bad_card("This card has expired")
    if exp_year > now.year + 20:
        bad_card("Check the expiry year")

    cvc = (cvc or "").strip()
    if not cvc.isdigit() or len(cvc) not in (3, 4):
        bad_card("Security code (CVC) should be 3 or 4 digits")

    return {"brand": brand, "last4": number[-4:], "number": number}


def charge_card(number: str, amount: Decimal) -> Optional[str]:
    """Pretend to charge the card. Returns None if it worked, or a reason if it was declined.

    In this demo every card is accepted. A real gateway would return its decline reason here.
    """
    return None


def new_reference() -> str:
    return f"QL-{secrets.token_hex(4).upper()}"


def next_period(paid_until: Optional[datetime], days: int, now: datetime):
    """A new payment starts when the current plan ends (or now, if there's no active plan)."""
    start = paid_until if paid_until and paid_until > now else now
    return start, start + timedelta(days=days)
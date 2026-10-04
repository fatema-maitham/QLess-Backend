# tests/test_bookings.py
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.service import ServiceModel
from tests.lib import login


def find_service(db: Session, name: str) -> ServiceModel:
    return db.query(ServiceModel).filter(ServiceModel.name == name).first()


def sign_up(test_app: TestClient, email: str):
    response = test_app.post(
        "/api/auth/sign-up",
        json={"name": "Booking Customer", "email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


def next_weekday(days_ahead: int = 3) -> str:
    """A date in the future that isn't a Friday (the bank is closed on Fridays)."""
    day = date.today() + timedelta(days=days_ahead)
    while day.strftime("%A") == "Friday":
        day += timedelta(days=1)
    return str(day)


def test_cannot_book_in_the_past(test_app: TestClient, test_db: Session, override_get_db):
    service = find_service(test_db, "General Check-up")
    customer = sign_up(test_app, "past@test.com")
    slot = {"booking_date": str(date.today() - timedelta(days=1)), "booking_time": "10:00"}

    response = test_app.post(f"/api/services/{service.id}/bookings", json=slot, headers=customer)

    assert response.status_code == 400


def test_cannot_book_outside_opening_hours(test_app: TestClient, test_db: Session, override_get_db):
    service = find_service(test_db, "General Check-up")  # clinic is open 09:00-21:00
    customer = sign_up(test_app, "late@test.com")
    slot = {"booking_date": next_weekday(), "booking_time": "22:30"}

    response = test_app.post(f"/api/services/{service.id}/bookings", json=slot, headers=customer)

    assert response.status_code == 400


def test_owner_cannot_book(test_app: TestClient, test_db: Session, override_get_db):
    service = find_service(test_db, "General Check-up")
    owner = login(test_app, "owner@qless.com")
    slot = {"booking_date": next_weekday(), "booking_time": "11:00"}

    response = test_app.post(f"/api/services/{service.id}/bookings", json=slot, headers=owner)

    assert response.status_code == 403


def test_staff_confirms_then_completes(test_app: TestClient, test_db: Session, override_get_db):
    service = find_service(test_db, "Card Services")  # Manama branch, where the seeded staff works
    customer = sign_up(test_app, "staffbook@test.com")
    staff = login(test_app, "staff@qless.com")
    slot = {"booking_date": next_weekday(), "booking_time": "09:00"}

    booked = test_app.post(f"/api/services/{service.id}/bookings", json=slot, headers=customer)
    assert booked.status_code == 201
    booking_id = booked.json()["id"]

    branch_list = test_app.get(f"/api/branches/{service.branch_id}/bookings", headers=staff)
    assert branch_list.status_code == 200
    assert booking_id in [b["id"] for b in branch_list.json()]

    too_early = test_app.patch(f"/api/bookings/{booking_id}", json={"status": "completed"}, headers=staff)
    assert too_early.status_code == 400  # must be confirmed first

    confirmed = test_app.patch(f"/api/bookings/{booking_id}", json={"status": "confirmed"}, headers=staff)
    assert confirmed.status_code == 200

    completed = test_app.patch(f"/api/bookings/{booking_id}", json={"status": "completed"}, headers=staff)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    titles = [n["title"] for n in test_app.get("/api/notifications", headers=customer).json()["notifications"]]
    assert "Booking confirmed" in titles
    assert "Booking completed" in titles


def test_customer_reschedule_goes_back_to_pending(test_app: TestClient, test_db: Session, override_get_db):
    service = find_service(test_db, "General Check-up")
    customer = sign_up(test_app, "move@test.com")
    owner = login(test_app, "owner@qless.com")
    slot = {"booking_date": next_weekday(), "booking_time": "12:00"}

    booking_id = test_app.post(f"/api/services/{service.id}/bookings", json=slot, headers=customer).json()["id"]
    test_app.patch(f"/api/bookings/{booking_id}", json={"status": "confirmed"}, headers=owner)

    moved = test_app.patch(f"/api/bookings/{booking_id}", json={"booking_time": "13:00"}, headers=customer)

    assert moved.status_code == 200
    assert moved.json()["status"] == "pending"  # the business must confirm the new time

    own_status = test_app.patch(f"/api/bookings/{booking_id}", json={"status": "confirmed"}, headers=customer)
    assert own_status.status_code == 403  # customers can't confirm their own booking


def test_other_customer_cannot_see_or_cancel(test_app: TestClient, test_db: Session, override_get_db):
    service = find_service(test_db, "General Check-up")
    customer = sign_up(test_app, "mine@test.com")
    stranger = sign_up(test_app, "stranger@test.com")
    slot = {"booking_date": next_weekday(), "booking_time": "14:00"}

    booking_id = test_app.post(f"/api/services/{service.id}/bookings", json=slot, headers=customer).json()["id"]

    assert test_app.get(f"/api/bookings/{booking_id}", headers=stranger).status_code == 403
    assert test_app.delete(f"/api/bookings/{booking_id}", headers=stranger).status_code == 403

    cancelled = test_app.delete(f"/api/bookings/{booking_id}", headers=customer)
    assert cancelled.status_code == 200

    again = test_app.delete(f"/api/bookings/{booking_id}", headers=customer)
    assert again.status_code == 400  # already cancelled
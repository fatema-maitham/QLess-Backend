# tests/test_join_and_book_rules.py
# Rules: one place at a time, no joining when the branch is closed,
# and no two bookings at the same time.
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.queue import QueueModel
from models.service import ServiceModel

BAHRAIN = ZoneInfo("Asia/Bahrain")


def sign_up(test_app: TestClient, email: str):
    response = test_app.post(
        "/api/auth/sign-up",
        json={"name": "Rules Customer", "email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


def find_queue(db: Session, name: str) -> QueueModel:
    return db.query(QueueModel).filter(QueueModel.name == name).first()


def find_service(db: Session, name: str) -> ServiceModel:
    return db.query(ServiceModel).filter(ServiceModel.name == name).first()


def next_weekday(days_ahead: int = 3) -> str:
    """A future date that isn't a Friday (the bank is closed on Fridays)."""
    day = date.today() + timedelta(days=days_ahead)
    while day.strftime("%A") == "Friday":
        day += timedelta(days=1)
    return str(day)


# ---------- Branch closed ----------

def test_cannot_join_on_a_closed_day(test_app: TestClient, test_db: Session, override_get_db, monkeypatch):
    queue = find_queue(test_db, "Accounts Queue")  # Manama bank: 08:00-14:00, closed on Fridays
    customer = sign_up(test_app, "friday@test.com")
    monkeypatch.setattr("services.opening_hours.now_local", lambda: datetime(2026, 10, 9, 10, 0, tzinfo=BAHRAIN))

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)

    assert response.status_code == 400
    assert "closed" in response.json()["detail"]


def test_cannot_join_after_closing_time(test_app: TestClient, test_db: Session, override_get_db, monkeypatch):
    queue = find_queue(test_db, "Accounts Queue")  # closes at 14:00
    customer = sign_up(test_app, "evening@test.com")
    monkeypatch.setattr("services.opening_hours.now_local", lambda: datetime(2026, 10, 5, 20, 0, tzinfo=BAHRAIN))

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)

    assert response.status_code == 400


def test_can_join_when_branch_is_open(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Accounts Queue")  # conftest says it's Monday 10:00
    customer = sign_up(test_app, "open@test.com")

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)

    assert response.status_code == 201


# ---------- One place at a time ----------

def test_cannot_wait_at_two_places(test_app: TestClient, test_db: Session, override_get_db):
    bank = find_queue(test_db, "Accounts Queue")  # Pearl Bank, Manama
    clinic = find_queue(test_db, "Walk-in Queue")  # Dilmun Clinic, Seef
    customer = sign_up(test_app, "twoplaces@test.com")

    joined = test_app.post(f"/api/queues/{bank.id}/entries", headers=customer)
    assert joined.status_code == 201

    blocked = test_app.post(f"/api/queues/{clinic.id}/entries", headers=customer)
    assert blocked.status_code == 400
    assert "already in a queue" in blocked.json()["detail"]

    # After leaving the bank queue, the clinic is fine
    assert test_app.delete(f"/api/queue-entries/{joined.json()['id']}", headers=customer).status_code == 200
    assert test_app.post(f"/api/queues/{clinic.id}/entries", headers=customer).status_code == 201


# ---------- Bookings ----------

def test_cannot_book_two_things_at_the_same_time(test_app: TestClient, test_db: Session, override_get_db):
    checkup = find_service(test_db, "General Check-up")  # clinic
    account = find_service(test_db, "Open an Account")  # bank
    customer = sign_up(test_app, "twobookings@test.com")
    slot = {"booking_date": next_weekday(), "booking_time": "10:00"}

    first = test_app.post(f"/api/services/{checkup.id}/bookings", json=slot, headers=customer)
    assert first.status_code == 201

    second = test_app.post(f"/api/services/{account.id}/bookings", json=slot, headers=customer)
    assert second.status_code == 409
    assert "another booking" in second.json()["detail"]

    # A different time is fine
    later = {**slot, "booking_time": "12:00"}
    assert test_app.post(f"/api/services/{account.id}/bookings", json=later, headers=customer).status_code == 201


def test_cannot_book_on_a_closed_day(test_app: TestClient, test_db: Session, override_get_db):
    account = find_service(test_db, "Open an Account")  # bank is closed on Fridays
    customer = sign_up(test_app, "fridaybook@test.com")

    day = date.today() + timedelta(days=3)
    while day.strftime("%A") != "Friday":
        day += timedelta(days=1)

    response = test_app.post(
        f"/api/services/{account.id}/bookings",
        json={"booking_date": str(day), "booking_time": "10:00"},
        headers=customer,
    )

    assert response.status_code == 400
    assert "closed" in response.json()["detail"]
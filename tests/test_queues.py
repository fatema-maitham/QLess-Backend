# tests/test_queues.py
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.business import BusinessModel
from models.queue import QueueModel
from models.service import ServiceModel
from models.user import UserModel
from tests.lib import login


def find_queue(db: Session, name: str) -> QueueModel:
    return db.query(QueueModel).filter(QueueModel.name == name).first()


def sign_up(test_app: TestClient, email: str):
    """Make a brand-new customer so a test doesn't affect the seeded one."""
    response = test_app.post(
        "/api/auth/sign-up",
        json={"name": "Test Customer", "email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


# ---------- Browse ----------

def test_browse_shows_only_approved(test_app: TestClient, test_db: Session, override_get_db):
    response = test_app.get("/api/businesses")

    assert response.status_code == 200
    names = [b["name"] for b in response.json()]
    assert "Pearl Bank" in names
    assert "Seef Salon" not in names  # pending business stays hidden


# ---------- Joining queues ----------

def test_customer_joins_queue(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Walk-in Queue")
    headers = login(test_app, "customer@qless.com")

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=headers)

    assert response.status_code == 201
    assert response.json()["queue_number"] == 1
    assert response.json()["position"] == 1

    again = test_app.post(f"/api/queues/{queue.id}/entries", headers=headers)
    assert again.status_code == 400  # already in this queue

    # Leave again, so this customer can join a queue at another place in the tests below
    left = test_app.delete(f"/api/queue-entries/{response.json()['id']}", headers=headers)
    assert left.status_code == 200


def test_cannot_join_closed_queue(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Cards Queue")
    headers = login(test_app, "customer@qless.com")

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=headers)

    assert response.status_code == 400


def test_owner_cannot_join_queue(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Walk-in Queue")
    headers = login(test_app, "owner@qless.com")

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=headers)

    assert response.status_code == 403


# ---------- Full visit ----------

def test_full_visit_then_review(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Accounts Queue")
    bank = test_db.query(BusinessModel).filter(BusinessModel.name == "Pearl Bank").first()
    customer = login(test_app, "customer@qless.com")
    staff = login(test_app, "staff@qless.com")

    joined = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)
    assert joined.status_code == 201
    entry_id = joined.json()["id"]

    called = test_app.post(f"/api/queues/{queue.id}/call-next", headers=staff)
    assert called.status_code == 200
    assert called.json()["entry"]["id"] == entry_id

    checked_in = test_app.patch(f"/api/queue-entries/{entry_id}", json={"status": "checked_in"}, headers=customer)
    assert checked_in.status_code == 200

    completed = test_app.patch(f"/api/queue-entries/{entry_id}", json={"status": "completed"}, headers=staff)
    assert completed.status_code == 200

    notifications = test_app.get("/api/notifications", headers=customer)
    assert notifications.json()["unread_count"] >= 1

    review = test_app.post(f"/api/businesses/{bank.id}/reviews", json={"rating": 5}, headers=customer)
    assert review.status_code == 201


# ---------- Categories ----------

def test_admin_creates_category(test_app: TestClient, test_db: Session, override_get_db):
    admin = login(test_app, "admin@qless.com")
    customer = login(test_app, "customer@qless.com")

    created = test_app.post("/api/categories", json={"name": "Education"}, headers=admin)
    assert created.status_code == 201

    duplicate = test_app.post("/api/categories", json={"name": "banking"}, headers=admin)
    assert duplicate.status_code == 409  # names are case-insensitive

    blocked = test_app.post("/api/categories", json={"name": "Hacked"}, headers=customer)
    assert blocked.status_code == 403


# ---------- Queue status (staff rules) ----------

def test_staff_can_pause_but_not_rename(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Accounts Queue")
    staff = login(test_app, "staff@qless.com")

    paused = test_app.patch(f"/api/queues/{queue.id}", json={"status": "paused"}, headers=staff)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    renamed = test_app.patch(f"/api/queues/{queue.id}", json={"name": "Hacked"}, headers=staff)
    assert renamed.status_code == 403

    resumed = test_app.patch(f"/api/queues/{queue.id}", json={"status": "open"}, headers=staff)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "open"


# ---------- Bookings ----------

def test_booking_flow(test_app: TestClient, test_db: Session, override_get_db):
    service = test_db.query(ServiceModel).filter(ServiceModel.name == "General Check-up").first()
    customer = login(test_app, "customer@qless.com")
    owner = login(test_app, "owner@qless.com")
    slot = {"booking_date": str(date.today() + timedelta(days=3)), "booking_time": "10:30"}

    booked = test_app.post(f"/api/services/{service.id}/bookings", json=slot, headers=customer)
    assert booked.status_code == 201
    assert booked.json()["status"] == "pending"
    booking_id = booked.json()["id"]

    taken = test_app.post(f"/api/services/{service.id}/bookings", json=slot, headers=customer)
    assert taken.status_code == 409  # same time already booked

    mine = test_app.get("/api/bookings/me", headers=customer)
    assert booking_id in [b["id"] for b in mine.json()]

    confirmed = test_app.patch(f"/api/bookings/{booking_id}", json={"status": "confirmed"}, headers=owner)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    cancelled = test_app.delete(f"/api/bookings/{booking_id}", headers=customer)
    assert cancelled.status_code == 200


# ---------- No-shows ----------

def test_two_no_shows_give_warning(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Accounts Queue")
    customer = sign_up(test_app, "noshow@test.com")
    staff = login(test_app, "staff@qless.com")

    for _ in range(2):
        joined = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)
        assert joined.status_code == 201
        entry_id = joined.json()["id"]

        assert test_app.post(f"/api/queues/{queue.id}/call-next", headers=staff).status_code == 200

        missed = test_app.patch(f"/api/queue-entries/{entry_id}", json={"status": "no_show"}, headers=staff)
        assert missed.status_code == 200
        assert missed.json()["status"] == "no_show"

    titles = [n["title"] for n in test_app.get("/api/notifications", headers=customer).json()["notifications"]]
    assert "Warning: one more no-show" in titles


def test_restricted_customer_cannot_join(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Accounts Queue")
    customer = sign_up(test_app, "banned@test.com")

    user = test_db.query(UserModel).filter(UserModel.email == "banned@test.com").first()
    user.restricted_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)
    test_db.commit()

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)

    assert response.status_code == 403
    assert "can't join queues" in response.json()["detail"]

    

# ---------- Counters ----------

def test_call_next_to_a_counter(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Teller Queue")
    owner = login(test_app, "owner@qless.com")
    customer = sign_up(test_app, "counter@test.com")

    updated = test_app.patch(f"/api/queues/{queue.id}", json={"counter_count": 2}, headers=owner)
    assert updated.status_code == 200
    assert updated.json()["counter_count"] == 2

    joined = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)
    assert joined.status_code == 201
    entry_id = joined.json()["id"]
    number = joined.json()["queue_number"]

    too_high = test_app.post(f"/api/queues/{queue.id}/call-next", json={"counter_number": 3}, headers=owner)
    assert too_high.status_code == 400

    called = test_app.post(f"/api/queues/{queue.id}/call-next", json={"counter_number": 2}, headers=owner)
    assert called.status_code == 200
    assert called.json()["entry"]["counter_number"] == 2
    assert called.json()["queue"]["now_serving"] == [
        {"counter_number": 2, "queue_number": number, "status": "called"}
    ]

    ticket = test_app.get(f"/api/queue-entries/{entry_id}", headers=customer)
    assert ticket.json()["counter_number"] == 2


def test_wait_is_shorter_with_more_counters(test_app: TestClient, test_db: Session, override_get_db):
    # Teller Queue now has 2 counters (test above) and 5 minutes per person
    queue = find_queue(test_db, "Teller Queue")

    for email in ["wait1@test.com", "wait2@test.com"]:
        joined = test_app.post(f"/api/queues/{queue.id}/entries", headers=sign_up(test_app, email))
        assert joined.status_code == 201

    third = test_app.post(f"/api/queues/{queue.id}/entries", headers=sign_up(test_app, "wait3@test.com"))

    assert third.json()["people_ahead"] == 2
    assert third.json()["estimated_wait_minutes"] == 5  # 2 people, 2 counters -> one round of 5 min


# ---------- Inactive places ----------

def test_cannot_join_when_branch_is_inactive(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Walk-in Queue")
    customer = sign_up(test_app, "inactive@test.com")

    queue.branch.is_active = False
    test_db.commit()

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)

    assert response.status_code == 400
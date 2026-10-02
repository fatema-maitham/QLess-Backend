# tests/test_queues.py
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.business import BusinessModel
from models.queue import QueueModel
from tests.lib import login


def find_queue(db: Session, name: str) -> QueueModel:
    return db.query(QueueModel).filter(QueueModel.name == name).first()


def test_browse_shows_only_approved(test_app: TestClient, test_db: Session, override_get_db):
    response = test_app.get("/api/businesses")

    assert response.status_code == 200
    names = [b["name"] for b in response.json()]
    assert "Pearl Bank" in names
    assert "Seef Salon" not in names  # pending business stays hidden


def test_customer_joins_queue(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Walk-in Queue")
    headers = login(test_app, "customer@qless.com")

    response = test_app.post(f"/api/queues/{queue.id}/entries", headers=headers)

    assert response.status_code == 201
    assert response.json()["queue_number"] == 1
    assert response.json()["position"] == 1

    again = test_app.post(f"/api/queues/{queue.id}/entries", headers=headers)
    assert again.status_code == 400  # already in this queue


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


def test_full_visit_then_review(test_app: TestClient, test_db: Session, override_get_db):
    queue = find_queue(test_db, "Accounts Queue")
    bank = test_db.query(BusinessModel).filter(BusinessModel.name == "Pearl Bank").first()
    customer = login(test_app, "customer@qless.com")
    staff = login(test_app, "staff@qless.com")

    # Customer joins
    joined = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer)
    assert joined.status_code == 201
    entry_id = joined.json()["id"]

    # Staff calls next
    called = test_app.post(f"/api/queues/{queue.id}/call-next", headers=staff)
    assert called.status_code == 200
    assert called.json()["entry"]["id"] == entry_id

    # Customer checks in, staff completes
    checked_in = test_app.patch(f"/api/queue-entries/{entry_id}", json={"status": "checked_in"}, headers=customer)
    assert checked_in.status_code == 200

    completed = test_app.patch(f"/api/queue-entries/{entry_id}", json={"status": "completed"}, headers=staff)
    assert completed.status_code == 200

    # Customer gets a notification and can now review
    notifications = test_app.get("/api/notifications", headers=customer)
    assert notifications.json()["unread_count"] >= 1

    review = test_app.post(f"/api/businesses/{bank.id}/reviews", json={"rating": 5}, headers=customer)
    assert review.status_code == 201
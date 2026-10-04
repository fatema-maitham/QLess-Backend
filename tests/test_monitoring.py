# tests/test_monitoring.py
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.queue import QueueModel
from tests.lib import login


def sign_up(test_app: TestClient, email: str):
    response = test_app.post(
        "/api/auth/sign-up",
        json={"name": "Monitor Customer", "email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_admin_sees_all_queues(test_app: TestClient, test_db: Session, override_get_db):
    admin = login(test_app, "admin@qless.com")

    all_queues = test_app.get("/api/admin/queues", headers=admin)
    open_queues = test_app.get("/api/admin/queues?status=open", headers=admin)

    assert all_queues.status_code == 200
    assert len(all_queues.json()) == test_db.query(QueueModel).count()
    assert all(q["status"] == "open" for q in open_queues.json())


def test_only_admin_can_monitor(test_app: TestClient, test_db: Session, override_get_db):
    owner = login(test_app, "owner@qless.com")

    assert test_app.get("/api/admin/queues", headers=owner).status_code == 403
    assert test_app.get("/api/admin/reviews", headers=owner).status_code == 403
    assert test_app.get("/api/admin/suspicious-activity", headers=owner).status_code == 403


def test_frequent_cancels_get_flagged_and_reviewed(test_app: TestClient, test_db: Session, override_get_db):
    queue = test_db.query(QueueModel).filter(QueueModel.name == "Walk-in Queue").first()
    customer = sign_up(test_app, "canceller@test.com")
    admin = login(test_app, "admin@qless.com")

    for _ in range(3):
        entry_id = test_app.post(f"/api/queues/{queue.id}/entries", headers=customer).json()["id"]
        assert test_app.delete(f"/api/queue-entries/{entry_id}", headers=customer).status_code == 200

    flags = test_app.get("/api/admin/suspicious-activity?status=open", headers=admin).json()
    mine = [f for f in flags if f["activity_type"] == "frequent_cancellations"]
    assert len(mine) == 1

    shown = test_app.get(f"/api/admin/suspicious-activity/{mine[0]['id']}", headers=admin)
    assert shown.status_code == 200

    reviewed = test_app.patch(
        f"/api/admin/suspicious-activity/{mine[0]['id']}",
        json={"status": "reviewed", "note": "Talked to the customer"},
        headers=admin,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"
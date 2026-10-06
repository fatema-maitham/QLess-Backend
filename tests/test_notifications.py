from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.queue import QueueModel
from tests.assignment_helpers import assigned_staff
from tests.lib import login


def sign_up(test_app: TestClient, email: str):
    response = test_app.post(
        "/api/auth/sign-up",
        json={
            "name": "Notify Customer",
            "email": email,
            "password": "secret123",
        },
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


def find_queue(db: Session, name: str) -> QueueModel:
    return (
        db.query(QueueModel)
        .filter(QueueModel.name == name)
        .first()
    )


def test_called_and_turn_approaching(
    test_app: TestClient, test_db: Session, override_get_db
):
    queue = find_queue(test_db, "Walk-in Queue")
    staff = assigned_staff(test_app, test_db, queue)
    first = sign_up(test_app, "first@test.com")
    second = sign_up(test_app, "second@test.com")

    test_app.post(
        f"/api/queues/{queue.id}/entries", headers=first
    )
    test_app.post(
        f"/api/queues/{queue.id}/entries", headers=second
    )

    assert test_app.post(
        f"/api/queues/{queue.id}/call-next",
        headers=staff,
    ).status_code == 200

    first_titles = [
        item["type"]
        for item in test_app.get(
            "/api/notifications", headers=first
        ).json()["notifications"]
    ]

    second_titles = [
        item["type"]
        for item in test_app.get(
            "/api/notifications", headers=second
        ).json()["notifications"]
    ]

    assert "called" in first_titles
    assert "turn_approaching" in second_titles


def test_mark_read_unread_and_delete(
    test_app: TestClient, test_db: Session, override_get_db
):
    customer = login(
        test_app, "first@test.com", "secret123"
    )

    data = test_app.get(
        "/api/notifications", headers=customer
    ).json()

    assert data["unread_count"] >= 1
    notification_id = data["notifications"][0]["id"]

    read = test_app.patch(
        f"/api/notifications/{notification_id}",
        json={"is_read": True},
        headers=customer,
    )
    assert read.status_code == 200
    assert read.json()["is_read"] is True

    unread = test_app.patch(
        f"/api/notifications/{notification_id}",
        json={"is_read": False},
        headers=customer,
    )
    assert unread.json()["is_read"] is False

    only_unread = test_app.get(
        "/api/notifications?unread_only=true",
        headers=customer,
    ).json()

    assert all(
        not item["is_read"]
        for item in only_unread["notifications"]
    )

    deleted = test_app.delete(
        f"/api/notifications/{notification_id}",
        headers=customer,
    )
    assert deleted.status_code == 200


def test_mark_all_read(
    test_app: TestClient, test_db: Session, override_get_db
):
    customer = login(
        test_app, "second@test.com", "secret123"
    )

    response = test_app.patch(
        "/api/notifications/read-all",
        headers=customer,
    )

    assert response.status_code == 200

    assert test_app.get(
        "/api/notifications",
        headers=customer,
    ).json()["unread_count"] == 0


def test_cannot_touch_someone_elses_notification(
    test_app: TestClient, test_db: Session, override_get_db
):
    owner_of_it = login(
        test_app, "second@test.com", "secret123"
    )
    stranger = sign_up(test_app, "nosy@test.com")

    notification_id = test_app.get(
        "/api/notifications",
        headers=owner_of_it,
    ).json()["notifications"][0]["id"]

    assert test_app.patch(
        f"/api/notifications/{notification_id}",
        json={"is_read": True},
        headers=stranger,
    ).status_code == 404

    assert test_app.delete(
        f"/api/notifications/{notification_id}",
        headers=stranger,
    ).status_code == 404


def test_notifications_need_login(
    test_app: TestClient, test_db: Session, override_get_db
):
    assert test_app.get(
        "/api/notifications"
    ).status_code in (401, 403)
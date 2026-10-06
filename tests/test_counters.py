from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.branch import BranchModel
from models.queue import QueueModel
from models.service import ServiceModel
from tests.assignment_helpers import assigned_staff
from tests.lib import login


def sign_up(test_app: TestClient, email: str):
    response = test_app.post(
        "/api/auth/sign-up",
        json={
            "name": "Counter Customer",
            "email": email,
            "password": "secret123",
        },
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


def make_open_queue(
    test_app: TestClient,
    db: Session,
    name: str,
    counters: int,
    minutes: int = 10,
) -> int:
    owner = login(test_app, "owner@qless.com")
    branch = (
        db.query(BranchModel)
        .filter(BranchModel.name == "Manama Branch")
        .first()
    )
    service = (
        db.query(ServiceModel)
        .filter(ServiceModel.name == "Open an Account")
        .first()
    )

    created = test_app.post(
        f"/api/branches/{branch.id}/queues",
        json={
            "name": name,
            "service_id": service.id,
            "counter_count": counters,
            "average_service_minutes": minutes,
        },
        headers=owner,
    )
    assert created.status_code == 201

    queue_id = created.json()["id"]

    opened = test_app.patch(
        f"/api/queues/{queue_id}",
        json={"status": "open"},
        headers=owner,
    )
    assert opened.status_code == 200

    return queue_id


def test_each_counter_calls_its_own_person(
    test_app: TestClient, test_db: Session, override_get_db
):
    queue_id = make_open_queue(
        test_app, test_db, "Three Desks", counters=3
    )
    queue = test_db.get(QueueModel, queue_id)

    for n in range(1, 5):
        test_app.post(
            f"/api/queues/{queue_id}/entries",
            headers=sign_up(test_app, f"desk{n}@test.com"),
        )

    for counter in [1, 2, 3]:
        called = test_app.post(
            f"/api/queues/{queue_id}/call-next",
            headers=assigned_staff(
                test_app, test_db, queue, counter
            ),
        )
        assert called.status_code == 200
        assert called.json()["entry"]["queue_number"] == counter

    serving = test_app.get(
        f"/api/queues/{queue_id}"
    ).json()["now_serving"]

    assert [
        (item["counter_number"], item["queue_number"])
        for item in serving
    ] == [(1, 1), (2, 2), (3, 3)]


def test_counter_must_finish_before_calling_again(
    test_app: TestClient, test_db: Session, override_get_db
):
    queue_id = make_open_queue(
        test_app, test_db, "One At A Time", counters=2
    )
    queue = test_db.get(QueueModel, queue_id)
    staff = assigned_staff(test_app, test_db, queue, 1)

    for n in range(1, 3):
        test_app.post(
            f"/api/queues/{queue_id}/entries",
            headers=sign_up(test_app, f"busy{n}@test.com"),
        )

    first = test_app.post(
        f"/api/queues/{queue_id}/call-next",
        headers=staff,
    )
    assert first.status_code == 200

    blocked = test_app.post(
        f"/api/queues/{queue_id}/call-next",
        headers=staff,
    )
    assert blocked.status_code == 400

    other_counter = test_app.post(
        f"/api/queues/{queue_id}/call-next",
        headers=assigned_staff(test_app, test_db, queue, 2),
    )
    assert other_counter.status_code == 200

    done = test_app.patch(
        f"/api/queue-entries/{first.json()['entry']['id']}",
        json={"status": "completed"},
        headers=staff,
    )
    assert done.status_code == 200

    test_app.post(
        f"/api/queues/{queue_id}/entries",
        headers=sign_up(test_app, "busy3@test.com"),
    )

    again = test_app.post(
        f"/api/queues/{queue_id}/call-next",
        headers=staff,
    )
    assert again.status_code == 200


def test_cannot_remove_a_busy_counter(
    test_app: TestClient, test_db: Session, override_get_db
):
    queue_id = make_open_queue(
        test_app, test_db, "Shrinking", counters=3
    )
    owner = login(test_app, "owner@qless.com")

    entry_id = test_app.post(
        f"/api/queues/{queue_id}/entries",
        headers=sign_up(test_app, "shrink@test.com"),
    ).json()["id"]

    queue = test_db.get(QueueModel, queue_id)
    staff = assigned_staff(test_app, test_db, queue, 3)

    called = test_app.post(
        f"/api/queues/{queue_id}/call-next",
        headers=staff,
    )
    assert called.status_code == 200

    blocked = test_app.patch(
        f"/api/queues/{queue_id}",
        json={"counter_count": 2},
        headers=owner,
    )
    assert blocked.status_code == 400

    test_app.patch(
        f"/api/queue-entries/{entry_id}",
        json={"status": "completed"},
        headers=staff,
    )

    allowed = test_app.patch(
        f"/api/queues/{queue_id}",
        json={"counter_count": 2},
        headers=owner,
    )
    assert allowed.status_code == 200


def test_wait_counts_free_counters(
    test_app: TestClient, test_db: Session, override_get_db
):
    queue_id = make_open_queue(
        test_app,
        test_db,
        "Wait Check",
        counters=3,
        minutes=10,
    )

    waits = [
        test_app.post(
            f"/api/queues/{queue_id}/entries",
            headers=sign_up(test_app, f"w{n}@test.com"),
        ).json()["estimated_wait_minutes"]
        for n in range(7)
    ]

    assert waits == [0, 0, 0, 10, 10, 10, 20]


def test_customer_in_two_queues_of_one_branch(
    test_app: TestClient, test_db: Session, override_get_db
):
    loans = make_open_queue(
        test_app, test_db, "Loans Desk", counters=2
    )
    cards = make_open_queue(
        test_app, test_db, "Cards Desk", counters=1
    )
    customer = sign_up(test_app, "twoqueues@test.com")

    assert test_app.post(
        f"/api/queues/{loans}/entries",
        headers=customer,
    ).status_code == 201

    assert test_app.post(
        f"/api/queues/{cards}/entries",
        headers=customer,
    ).status_code == 201

    active = test_app.get(
        "/api/queue-entries/me",
        headers=customer,
    ).json()["active"]

    assert sorted(
        ticket["queue_name"] for ticket in active
    ) == ["Cards Desk", "Loans Desk"]
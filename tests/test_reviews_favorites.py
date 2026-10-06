from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.business import BusinessModel
from models.queue import QueueModel
from tests.assignment_helpers import assigned_staff
from tests.lib import login


def sign_up(test_app: TestClient, email: str):
    response = test_app.post(
        "/api/auth/sign-up",
        json={
            "name": "Review Customer",
            "email": email,
            "password": "secret123",
        },
    )
    return {"Authorization": f"Bearer {response.json()['token']}"}


def find_business(db: Session, name: str) -> BusinessModel:
    return (
        db.query(BusinessModel)
        .filter(BusinessModel.name == name)
        .first()
    )


def finish_a_visit(
    test_app: TestClient, db: Session, customer: dict
):
    """Complete a clinic visit before reviewing."""
    queue = (
        db.query(QueueModel)
        .filter(QueueModel.name == "Walk-in Queue")
        .first()
    )
    staff = assigned_staff(test_app, db, queue)

    entry_id = test_app.post(
        f"/api/queues/{queue.id}/entries",
        headers=customer,
    ).json()["id"]

    assert test_app.post(
        f"/api/queues/{queue.id}/call-next",
        headers=staff,
    ).status_code == 200

    done = test_app.patch(
        f"/api/queue-entries/{entry_id}",
        json={"status": "completed"},
        headers=staff,
    )
    assert done.status_code == 200


def test_cannot_review_without_a_visit(
    test_app: TestClient, test_db: Session, override_get_db
):
    clinic = find_business(test_db, "Dilmun Clinic")
    customer = sign_up(test_app, "novisit@test.com")

    response = test_app.post(
        f"/api/businesses/{clinic.id}/reviews",
        json={"rating": 5},
        headers=customer,
    )
    assert response.status_code == 403


def test_review_after_visit_then_edit_and_delete(
    test_app: TestClient, test_db: Session, override_get_db
):
    clinic = find_business(test_db, "Dilmun Clinic")
    customer = sign_up(test_app, "reviewer@test.com")
    finish_a_visit(test_app, test_db, customer)

    created = test_app.post(
        f"/api/businesses/{clinic.id}/reviews",
        json={
            "rating": 4,
            "comment": "Quick and friendly",
        },
        headers=customer,
    )
    assert created.status_code == 201
    review_id = created.json()["id"]

    twice = test_app.post(
        f"/api/businesses/{clinic.id}/reviews",
        json={"rating": 3},
        headers=customer,
    )
    assert twice.status_code == 409

    public = test_app.get(
        f"/api/businesses/{clinic.id}/reviews"
    )
    assert public.status_code == 200
    assert public.json()["review_count"] >= 1

    edited = test_app.patch(
        f"/api/reviews/{review_id}",
        json={"rating": 5},
        headers=customer,
    )
    assert edited.status_code == 200
    assert edited.json()["rating"] == 5

    deleted = test_app.delete(
        f"/api/reviews/{review_id}",
        headers=customer,
    )
    assert deleted.status_code == 200


def test_only_author_or_admin_can_change_a_review(
    test_app: TestClient, test_db: Session, override_get_db
):
    clinic = find_business(test_db, "Dilmun Clinic")
    author = sign_up(test_app, "author@test.com")
    stranger = sign_up(test_app, "notauthor@test.com")
    admin = login(test_app, "admin@qless.com")

    finish_a_visit(test_app, test_db, author)

    review_id = test_app.post(
        f"/api/businesses/{clinic.id}/reviews",
        json={"rating": 1, "comment": "rude words"},
        headers=author,
    ).json()["id"]

    assert test_app.patch(
        f"/api/reviews/{review_id}",
        json={"rating": 5},
        headers=stranger,
    ).status_code == 403

    assert test_app.delete(
        f"/api/reviews/{review_id}",
        headers=stranger,
    ).status_code == 403

    listed = test_app.get(
        "/api/admin/reviews", headers=admin
    )
    assert review_id in [
        review["id"] for review in listed.json()
    ]

    removed = test_app.delete(
        f"/api/reviews/{review_id}", headers=admin
    )
    assert removed.status_code == 200


def test_rating_must_be_1_to_5(
    test_app: TestClient, test_db: Session, override_get_db
):
    clinic = find_business(test_db, "Dilmun Clinic")
    customer = sign_up(test_app, "sixstars@test.com")

    response = test_app.post(
        f"/api/businesses/{clinic.id}/reviews",
        json={"rating": 6},
        headers=customer,
    )
    assert response.status_code == 422


def test_add_list_and_remove_favorite(
    test_app: TestClient, test_db: Session, override_get_db
):
    bank = find_business(test_db, "Pearl Bank")
    customer = sign_up(test_app, "fav@test.com")

    added = test_app.post(
        "/api/favorites",
        json={"business_id": bank.id},
        headers=customer,
    )
    assert added.status_code == 201

    duplicate = test_app.post(
        "/api/favorites",
        json={"business_id": bank.id},
        headers=customer,
    )
    assert duplicate.status_code == 409

    listed = test_app.get(
        "/api/favorites", headers=customer
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    removed = test_app.delete(
        f"/api/favorites/{bank.id}",
        headers=customer,
    )
    assert removed.status_code == 200
    assert test_app.get(
        "/api/favorites", headers=customer
    ).json() == []

    again = test_app.delete(
        f"/api/favorites/{bank.id}",
        headers=customer,
    )
    assert again.status_code == 404


def test_cannot_favorite_pending_business(
    test_app: TestClient, test_db: Session, override_get_db
):
    salon = find_business(test_db, "Seef Salon")
    customer = sign_up(test_app, "favpending@test.com")

    response = test_app.post(
        "/api/favorites",
        json={"business_id": salon.id},
        headers=customer,
    )
    assert response.status_code == 400


def test_owner_cannot_use_favorites(
    test_app: TestClient, test_db: Session, override_get_db
):
    owner = login(test_app, "owner@qless.com")

    assert test_app.get(
        "/api/favorites", headers=owner
    ).status_code == 403
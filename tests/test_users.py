# tests/test_users.py
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.user import UserModel
from tests.lib import login


def test_sign_up(test_app: TestClient, test_db: Session, override_get_db):
    data = {"name": "New Person", "email": "new@test.com", "password": "secret123"}

    response = test_app.post("/api/auth/sign-up", json=data)

    assert response.status_code == 201
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == "new@test.com"
    assert body["user"]["role"] == "customer"
    assert test_db.query(UserModel).filter(UserModel.email == "new@test.com").first()


def test_sign_up_duplicate_email(test_app: TestClient, test_db: Session, override_get_db):
    data = {"name": "Copy", "email": "customer@qless.com", "password": "secret123"}

    response = test_app.post("/api/auth/sign-up", json=data)

    assert response.status_code == 409


def test_sign_in_wrong_password(test_app: TestClient, test_db: Session, override_get_db):
    response = test_app.post(
        "/api/auth/sign-in", json={"email": "customer@qless.com", "password": "wrong"}
    )

    assert response.status_code == 401


def test_get_me(test_app: TestClient, test_db: Session, override_get_db):
    headers = login(test_app, "customer@qless.com")

    response = test_app.get("/api/users/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "customer@qless.com"
    assert response.json()["role"] == "customer"


def test_get_me_without_token(test_app: TestClient, test_db: Session, override_get_db):
    response = test_app.get("/api/users/me")

    assert response.status_code in (401, 403)
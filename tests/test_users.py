from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.user import UserModel
from tests.lib import login


def test_register_user(
    test_app: TestClient,
    test_db: Session,
    override_get_db,
):
    # Data for registering a new user
    user_data = {
        "username": "registerTestUser123",
        "email": "register-test@example.com",
        "password": "mys3cretp2ssw0rd",
    }

    # Send a POST request to register the user
    response = test_app.post("/api/register", json=user_data)

    # Verify that registration succeeds and returns a token
    assert response.status_code == 201
    data = response.json()
    assert isinstance(data["token"], str)
    assert data["token"]
    assert data["message"] == "Login successful"

    # Verify the user was created in the database
    user = (
        test_db.query(UserModel)
        .filter(UserModel.username == user_data["username"])
        .first()
    )
    assert user is not None
    assert user.username == user_data["username"]
    assert user.email == user_data["email"]


def test_get_current_user(
    test_app: TestClient,
    test_db: Session,
    override_get_db,
):
    # Create a new mock user in the test database
    user = UserModel(
        username="currentUser123",
        email="current-user@example.com",
    )
    user.set_password("mys3cretp2ssw0rd")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Use the login helper to generate authentication headers
    headers = login(test_app, "currentUser123", "mys3cretp2ssw0rd")

    # Send a GET request for the authenticated user
    response = test_app.get("/api/current_user", headers=headers)

    # Verify the response contains the correct user
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["username"] == user.username
    assert data["email"] == user.email
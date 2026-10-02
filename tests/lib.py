# tests/lib.py
from fastapi.testclient import TestClient

from data.category_data import create_categories
from data.business_data import create_businesses
from data.role_data import create_roles
from data.user_data import create_users

PASSWORD = "password123"


def seed_db(db):
    roles = create_roles()
    db.add_all(roles.values())

    users = create_users(roles)
    db.add_all(users.values())

    categories = create_categories()
    db.add_all(categories.values())

    db.add_all(create_businesses(users, categories))
    db.commit()


def login(test_app: TestClient, email: str, password: str = PASSWORD):
    response = test_app.post("/api/auth/sign-in", json={"email": email, "password": password})

    if response.status_code != 200:
        raise Exception(f"Login failed: {response.json().get('detail', 'Unknown error')}")

    return {"Authorization": f"Bearer {response.json()['token']}"}
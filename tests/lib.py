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


# A test Visa number that passes the card check
TEST_CARD = {
    "card_holder": "Test Owner",
    "card_number": "4242 4242 4242 4242",
    "exp_month": 12,
    "exp_year": 2035,
    "cvc": "123",
}


def pay_for_business(test_app: TestClient, headers, business_id: int, plan: str = "monthly"):
    """Pay for a plan. Paying also sends a draft business for approval."""
    response = test_app.post(
        f"/api/businesses/{business_id}/payments",
        json={"plan": plan, **TEST_CARD},
        headers=headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()
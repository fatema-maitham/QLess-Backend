from tests.lib import TEST_CARD, login, pay_for_business


# ---------- helpers ----------

def create_business(test_app, headers, name):
    response = test_app.post("/api/businesses", json={"name": name, "category_id": 1}, headers=headers)
    assert response.status_code == 201
    return response.json()


def pay(test_app, headers, business_id, **changes):
    body = {"plan": "monthly", **TEST_CARD, **changes}
    return test_app.post(f"/api/businesses/{business_id}/payments", json=body, headers=headers)


# ---------- plans ----------

def test_plans_are_public(test_app, override_get_db):
    response = test_app.get("/api/payments/plans")
    assert response.status_code == 200
    ids = [plan["id"] for plan in response.json()]
    assert ids == ["monthly", "yearly"]
    assert response.json()[0]["currency"] == "BHD"


# ---------- paying ----------

def test_new_business_is_not_paid(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Unpaid Cafe")
    assert business["is_paid"] is False
    assert business["paid_until"] is None


def test_pay_sends_business_for_approval(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Paying Cafe")

    payment = pay_for_business(test_app, owner, business["id"])
    assert payment["status"] == "paid"
    assert payment["amount"] == 15.0
    assert payment["card_last4"] == "4242"
    assert payment["card_brand"] == "visa"
    assert payment["reference"].startswith("QL-")

    response = test_app.get(f"/api/businesses/{business['id']}", headers=owner)
    assert response.json()["approval_status"] == "pending"
    assert response.json()["is_paid"] is True
    assert response.json()["current_plan"] == "monthly"


def test_full_card_number_is_never_returned(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Private Card Cafe")
    payment = pay_for_business(test_app, owner, business["id"])

    text = str(payment)
    assert "4242424242424242" not in text
    assert "cvc" not in payment


def test_renewing_adds_time_on_top(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Renew Cafe")

    first = pay_for_business(test_app, owner, business["id"])
    second = pay_for_business(test_app, owner, business["id"], plan="yearly")

    # The yearly plan starts when the monthly one ends
    assert second["period_start"] == first["period_end"]

    response = test_app.get(f"/api/businesses/{business['id']}/subscription", headers=owner)
    assert response.json()["plan"] == "yearly"
    assert response.json()["days_left"] >= 394


def test_any_card_number_works(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Any Card Cafe")

    response = pay(test_app, owner, business["id"], card_number="1234 5678 9012 3456")
    assert response.status_code == 201
    assert response.json()["card_last4"] == "3456"
    assert response.json()["card_brand"] is None


def test_short_card_number_is_rejected(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Short Card Cafe")

    response = pay(test_app, owner, business["id"], card_number="1234 5678 90")
    assert response.status_code == 400


def test_expired_card_is_rejected(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Old Card Cafe")

    response = pay(test_app, owner, business["id"], exp_month=1, exp_year=2020)
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]


def test_owner_cannot_pay_for_someone_elses_business(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Not Yours Cafe")

    other = test_app.post(
        "/api/auth/sign-up",
        json={"name": "Other", "email": "pay.other@test.com", "password": "password123", "role": "owner"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['token']}"}

    assert pay(test_app, other_headers, business["id"]).status_code == 403
    assert test_app.get(f"/api/businesses/{business['id']}/payments", headers=other_headers).status_code == 403


def test_customer_cannot_pay(test_app, override_get_db):
    customer = login(test_app, "customer@qless.com")
    assert pay(test_app, customer, 1).status_code == 403


# ---------- admin ----------

def test_admin_sees_all_payments(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    admin = login(test_app, "admin@qless.com")
    business = create_business(test_app, owner, "Admin View Cafe")
    payment = pay_for_business(test_app, owner, business["id"])

    response = test_app.get("/api/admin/payments", headers=admin)
    assert response.status_code == 200
    row = next(p for p in response.json() if p["id"] == payment["id"])
    assert row["business"]["name"] == "Admin View Cafe"
    assert row["owner"]["email"] == "owner@qless.com"

    response = test_app.get("/api/admin/payments", params={"status": "failed"}, headers=admin)
    assert all(p["status"] == "failed" for p in response.json())

    response = test_app.get("/api/admin/payments", params={"search": "Admin View"}, headers=admin)
    assert [p["id"] for p in response.json()] == [payment["id"]]


def test_admin_dashboard_shows_revenue(test_app, override_get_db):
    admin = login(test_app, "admin@qless.com")
    stats = test_app.get("/api/admin/dashboard", headers=admin).json()
    assert stats["revenue_total"] > 0
    assert stats["paid_payments"] >= 1
    assert stats["active_plans"] >= 1


def test_owner_cannot_see_admin_payments(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    assert test_app.get("/api/admin/payments", headers=owner).status_code == 403
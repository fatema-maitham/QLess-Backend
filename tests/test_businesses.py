from tests.lib import login


# ---------- helpers ----------

def sign_up(test_app, name, email, role="customer"):
    response = test_app.post(
        "/api/auth/sign-up",
        json={"name": name, "email": email, "password": "password123", "role": role},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['token']}"}


def create_business(test_app, headers, name="Test Cafe"):
    response = test_app.post("/api/businesses", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()


def create_branch(test_app, headers, business_id, name="Main Branch"):
    response = test_app.post(f"/api/businesses/{business_id}/branches", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()


# ---------- businesses ----------

def test_owner_creates_business_as_draft(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Draft Cafe")
    assert business["approval_status"] == "draft"

    response = test_app.get("/api/users/me/businesses", headers=owner)
    assert response.status_code == 200
    assert business["id"] in [b["id"] for b in response.json()]


def test_customer_cannot_create_business(test_app, override_get_db):
    customer = login(test_app, "customer@qless.com")
    response = test_app.post("/api/businesses", json={"name": "Not Allowed"}, headers=customer)
    assert response.status_code == 403


def test_draft_business_hidden_from_public(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Hidden Cafe")

    assert test_app.get(f"/api/businesses/{business['id']}").status_code == 404
    assert test_app.get(f"/api/businesses/{business['id']}", headers=owner).status_code == 200


def test_submit_business_for_approval(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Submit Cafe")

    response = test_app.patch(f"/api/businesses/{business['id']}", json={"approval_status": "pending"}, headers=owner)
    assert response.status_code == 200
    assert response.json()["approval_status"] == "pending"

    # Can't submit twice
    response = test_app.patch(f"/api/businesses/{business['id']}", json={"approval_status": "pending"}, headers=owner)
    assert response.status_code == 400


def test_owner_cannot_edit_another_owners_business(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Mine Cafe")

    other_owner = sign_up(test_app, "Other Owner", "other.owner@test.com", role="owner")
    response = test_app.patch(f"/api/businesses/{business['id']}", json={"name": "Stolen"}, headers=other_owner)
    assert response.status_code == 403


def test_deactivate_business(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Closing Cafe")

    assert test_app.delete(f"/api/businesses/{business['id']}", headers=owner).status_code == 200

    response = test_app.get(f"/api/businesses/{business['id']}", headers=owner)
    assert response.json()["is_active"] is False


# ---------- branches, services, hours ----------

def test_branch_services_and_hours(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Branchy Cafe")
    branch = create_branch(test_app, owner, business["id"], "Seef Branch")

    # Service
    response = test_app.post(
        f"/api/branches/{branch['id']}/services",
        json={"name": "Espresso", "duration_minutes": 5},
        headers=owner,
    )
    assert response.status_code == 201

    response = test_app.post(
        f"/api/branches/{branch['id']}/services",
        json={"name": "Bad", "duration_minutes": 0},
        headers=owner,
    )
    assert response.status_code == 422

    # Operating hours: one row per day
    hours = {"day_of_week": "monday", "open_time": "09:00", "close_time": "17:00"}
    assert test_app.post(f"/api/branches/{branch['id']}/hours", json=hours, headers=owner).status_code == 201
    assert test_app.post(f"/api/branches/{branch['id']}/hours", json=hours, headers=owner).status_code == 409

    # Branch details include "open now"
    response = test_app.get(f"/api/branches/{branch['id']}", headers=owner)
    assert response.status_code == 200
    assert "is_open_now" in response.json()


# ---------- staff ----------

def test_staff_add_and_deactivate(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Staffed Cafe")
    branch = create_branch(test_app, owner, business["id"], "Staffed Branch")
    sign_up(test_app, "New Staff", "new.staff@test.com")

    # Add them as staff
    response = test_app.post(
        f"/api/branches/{branch['id']}/staff",
        json={"user_email": "new.staff@test.com", "position": "Cashier"},
        headers=owner,
    )
    assert response.status_code == 201
    staff_id = response.json()["id"]

    # Their role is now staff, and they can see their branch
    staff_headers = login(test_app, "new.staff@test.com")
    response = test_app.get("/api/staff/me", headers=staff_headers)
    assert response.status_code == 200
    assert response.json()["branch"]["id"] == branch["id"]

    # Can't add the same person twice, or someone without an account
    response = test_app.post(
        f"/api/branches/{branch['id']}/staff", json={"user_email": "new.staff@test.com"}, headers=owner
    )
    assert response.status_code == 409
    response = test_app.post(
        f"/api/branches/{branch['id']}/staff", json={"user_email": "nobody@test.com"}, headers=owner
    )
    assert response.status_code == 404

    # Deactivate: they go back to customer
    assert test_app.delete(f"/api/staff/{staff_id}", headers=owner).status_code == 200
    response = test_app.post(
        "/api/auth/sign-in", json={"email": "new.staff@test.com", "password": "password123"}
    )
    assert response.json()["user"]["role"] == "customer"


# ---------- announcements ----------

def test_announcements(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    business = create_business(test_app, owner, "Announcing Cafe")

    response = test_app.post(
        f"/api/businesses/{business['id']}/announcements",
        json={"title": "Opening", "message": "20% off"},
        headers=owner,
    )
    assert response.status_code == 201
    announcement_id = response.json()["id"]
    assert response.json()["branch_id"] is None

    # A branch that isn't this business's
    response = test_app.post(
        f"/api/businesses/{business['id']}/announcements",
        json={"title": "Bad", "message": "Wrong branch", "branch_id": 99999},
        headers=owner,
    )
    assert response.status_code == 400

    # Deactivate
    assert test_app.delete(f"/api/announcements/{announcement_id}", headers=owner).status_code == 200
    response = test_app.get(f"/api/businesses/{business['id']}/announcements", headers=owner)
    assert response.json()[0]["is_active"] is False
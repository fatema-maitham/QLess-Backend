from tests.lib import login


# ---------- helpers ----------

def submit_business(test_app, owner, name):
    """Create a business and submit it for approval. Returns its id."""
    response = test_app.post("/api/businesses", json={"name": name, "category_id": 1}, headers=owner)
    assert response.status_code == 201
    business_id = response.json()["id"]

    response = test_app.patch(f"/api/businesses/{business_id}", json={"approval_status": "pending"}, headers=owner)
    assert response.status_code == 200
    return business_id


# ---------- access ----------

def test_non_admin_is_blocked(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    assert test_app.get("/api/admin/dashboard", headers=owner).status_code == 403


def test_dashboard(test_app, override_get_db):
    admin = login(test_app, "admin@qless.com")
    response = test_app.get("/api/admin/dashboard", headers=admin)
    assert response.status_code == 200
    assert response.json()["users_total"] >= 4
    assert "admin" in response.json()["users_by_role"]


# ---------- business approvals ----------

def test_reject_needs_reason_and_notifies_owner(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    admin = login(test_app, "admin@qless.com")
    business_id = submit_business(test_app, owner, "Reject Me Cafe")

    response = test_app.patch(f"/api/admin/businesses/{business_id}", json={"approval_status": "rejected"}, headers=admin)
    assert response.status_code == 400

    response = test_app.patch(
        f"/api/admin/businesses/{business_id}",
        json={"approval_status": "rejected", "rejection_reason": "Add a description"},
        headers=admin,
    )
    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"
    assert response.json()["rejection_reason"] == "Add a description"

    response = test_app.get("/api/notifications", headers=owner)
    assert "Business rejected" in response.text


def test_cannot_approve_a_draft(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    admin = login(test_app, "admin@qless.com")
    response = test_app.post("/api/businesses", json={"name": name, "category_id": 1}, headers=owner)json={"name": "Still Draft Cafe", "category_id": 1}, headers=owner)
    business_id = response.json()["id"]

    response = test_app.patch(f"/api/admin/businesses/{business_id}", json={"approval_status": "approved"}, headers=admin)
    assert response.status_code == 400


def test_approve_makes_business_public(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    admin = login(test_app, "admin@qless.com")
    business_id = submit_business(test_app, owner, "Approved Cafe")

    response = test_app.patch(f"/api/admin/businesses/{business_id}", json={"approval_status": "approved"}, headers=admin)
    assert response.status_code == 200
    assert response.json()["approval_status"] == "approved"

    assert "Approved Cafe" in test_app.get("/api/businesses").text


# ---------- users ----------

def test_deactivate_and_reactivate_user(test_app, override_get_db):
    admin = login(test_app, "admin@qless.com")
    response = test_app.post(
        "/api/auth/sign-up",
        json={"name": "Temp User", "email": "temp.user@test.com", "password": "password123"},
    )
    user_id = response.json()["user"]["id"]
    credentials = {"email": "temp.user@test.com", "password": "password123"}

    assert test_app.patch(f"/api/admin/users/{user_id}", json={"is_active": False}, headers=admin).status_code == 200
    assert test_app.post("/api/auth/sign-in", json=credentials).status_code == 403

    assert test_app.patch(f"/api/admin/users/{user_id}", json={"is_active": True}, headers=admin).status_code == 200
    assert test_app.post("/api/auth/sign-in", json=credentials).status_code == 200


def test_set_and_lift_restriction(test_app, override_get_db):
    admin = login(test_app, "admin@qless.com")
    customer = login(test_app, "customer@qless.com")
    customer_id = test_app.get("/api/users/me", headers=customer).json()["id"]

    response = test_app.patch(
        f"/api/admin/users/{customer_id}", json={"restricted_until": "2030-01-01T00:00:00"}, headers=admin
    )
    assert response.json()["restricted_until"] is not None

    response = test_app.patch(f"/api/admin/users/{customer_id}", json={"restricted_until": None}, headers=admin)
    assert response.json()["restricted_until"] is None


def test_admin_cannot_deactivate_self(test_app, override_get_db):
    admin = login(test_app, "admin@qless.com")
    admin_id = test_app.get("/api/users/me", headers=admin).json()["id"]

    response = test_app.patch(f"/api/admin/users/{admin_id}", json={"is_active": False}, headers=admin)
    assert response.status_code == 400


# ---------- branches ----------

def test_admin_deactivates_branch(test_app, override_get_db):
    owner = login(test_app, "owner@qless.com")
    admin = login(test_app, "admin@qless.com")
    business_id = test_app.post("/api/businesses", json={"name": "Branch Cafe", "category_id": 1}, headers=owner).json()["id"]
    branch_id = test_app.post(
        f"/api/businesses/{business_id}/branches", json={"name": "Admin Test Branch"}, headers=owner
    ).json()["id"]

    response = test_app.patch(f"/api/admin/branches/{branch_id}", json={"is_active": False}, headers=admin)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


# ---------- audit logs ----------

def test_audit_logs_record_admin_actions(test_app, override_get_db):
    """Runs last in this file, so the actions above are already logged."""
    admin = login(test_app, "admin@qless.com")
    response = test_app.get("/api/admin/audit-logs", headers=admin)
    assert response.status_code == 200

    actions = [log["action"] for log in response.json()]
    for expected in ("reject_business", "approve_business", "deactivate_user", "lift_restriction", "deactivate_branch"):
        assert expected in actions

    response = test_app.get("/api/admin/audit-logs?entity_type=business", headers=admin)
    assert all(log["entity_type"] == "business" for log in response.json())
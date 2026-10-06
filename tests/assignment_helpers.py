from models.staff import StaffModel
from models.user import UserModel
from tests.lib import login


def assigned_staff(test_app, db, queue, counter=1):
    """Create a test staff member for this queue and counter."""
    email = f"assigned-{queue.id}-{counter}@test.com"

    user = db.query(UserModel).filter(UserModel.email == email).first()

    if user is None:
        response = test_app.post(
            "/api/auth/sign-up",
            json={
                "name": "Assigned Staff",
                "email": email,
                "password": "secret123",
            },
        )
        assert response.status_code == 201, response.text

        user = db.query(UserModel).filter(UserModel.email == email).first()
        seeded_staff = (
            db.query(UserModel)
            .filter(UserModel.email == "staff@qless.com")
            .one()
        )

        user.role_id = seeded_staff.role_id

        db.add(
            StaffModel(
                user_id=user.id,
                business_id=queue.business_id,
                branch_id=queue.branch_id,
                queue_id=queue.id,
                counter_number=counter,
                position="Receptionist",
                is_active=True,
            )
        )
        db.commit()

    return login(test_app, email, "secret123")
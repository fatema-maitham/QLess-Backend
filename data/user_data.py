from models.user import UserModel

# Every test user has the password: password123


def create_users(roles):
    people = [
        ("admin", "Admin User", "admin@qless.com", "33000001"),
        ("owner", "Owner User", "owner@qless.com", "33000002"),
        ("staff", "Staff User", "staff@qless.com", "33000003"),
        ("customer", "Customer User", "customer@qless.com", "33000004"),
    ]

    users = {}
    for role_name, name, email, phone in people:
        user = UserModel(name=name, email=email, phone=phone, role=roles[role_name])
        user.set_password("password123")
        users[role_name] = user

    return users
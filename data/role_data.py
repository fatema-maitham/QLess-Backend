from models.role import RoleModel


def create_roles():
    return {
        "customer": RoleModel(name="customer", description="Joins queues, books services, leaves reviews"),
        "owner": RoleModel(name="owner", description="Manages businesses, branches, services, queues and staff"),
        "staff": RoleModel(name="staff", description="Manages queues at an assigned branch"),
        "admin": RoleModel(name="admin", description="Manages the whole QLess platform"),
    }
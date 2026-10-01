# dependencies/roles.py
from fastapi import Depends, HTTPException, status

from dependencies.get_current_user import get_current_user
from models.user import UserModel


def require_roles(*allowed_roles: str):
    """Only let users with one of these roles in.

    Example:
        @router.post("/businesses")
        def create_business(user: UserModel = Depends(require_roles("owner"))):
            ...
    """

    def checker(user: UserModel = Depends(get_current_user)) -> UserModel:
        if user.role.name not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to do this")
        return user

    return checker


# Ready-made shortcuts so routes stay short
require_customer = require_roles("customer")
require_owner = require_roles("owner")
require_staff = require_roles("staff")
require_admin = require_roles("admin")
require_owner_or_staff = require_roles("owner", "staff")
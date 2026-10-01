from typing import Optional

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config.environment import JWT_SECRET
from database import get_db
from models.user import UserModel

# auto_error=False means: no token is OK, don't block the request
optional_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
) -> Optional[UserModel]:
    if not credentials:
        return None

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload.get("sub"))
    except (jwt.InvalidTokenError, TypeError, ValueError):
        return None

    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user or not user.is_active:
        return None

    return user
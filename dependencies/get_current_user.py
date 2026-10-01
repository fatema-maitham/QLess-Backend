from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from models.user import UserModel
from database import get_db
import jwt
from jwt import DecodeError, ExpiredSignatureError  # We import specific exceptions to handle them explicitly
from jwt.exceptions import InvalidSubjectError
from config.environment import JWT_SECRET

# FastAPI helper to extract the tokent from the auth headers : "Bearer ...."
http_bearer = HTTPBearer()

# TODO: fix the typing for the token
def get_current_user(db: Session = Depends(get_db), token: str = Depends(http_bearer)):
  try:
    # Decode the token using the secret key
    payload = jwt.decode(token.credentials, JWT_SECRET, algorithms=["HS256"])
    current_user_id =  payload.get("sub")

    user = db.query(UserModel).filter(UserModel.id == current_user_id).first()

    if not user:
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                              detail="Invalid username or password")
  except DecodeError as err:
     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                          detail=f'Could not decode token: {str(err)}')

  # Handle expired token errors
  except ExpiredSignatureError:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail='Token has expired')

  except InvalidSubjectError:
     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='Token invalid')
  return user




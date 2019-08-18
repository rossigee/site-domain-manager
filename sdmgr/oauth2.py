from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from starlette.status import HTTP_401_UNAUTHORIZED

from pydantic import BaseModel

import jwt

import os
import datetime
from datetime import timedelta, datetime


# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "b8b40f3b2d265e2f2757f7f6ffbbd61592069a69dbd168afc290e0bb611a8a8b"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class User(BaseModel):
    username: str


class UnauthorisedException(HTTPException):
    def __init__(self, *args, **kwargs):
        kwargs['status_code'] = HTTP_401_UNAUTHORIZED
        kwargs['detail'] = "Invalid OAuth2 bearer token."
        kwargs['headers'] = {"WWW-Authenticate": "Bearer"}
        return super(UnauthorisedException, *args, **kwargs)

openapi_prefix = os.getenv("OPENAPI_PREFIX", "")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{openapi_prefix}/token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = {
            "username": username
        }
        return User(**user)
    except jwt.PyJWTError:
        raise credentials_exception


def create_access_token(*, data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

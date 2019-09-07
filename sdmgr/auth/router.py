from fastapi import APIRouter, Depends, File
from fastapi.security import OAuth2PasswordRequestForm

from sdmgr.oauth2 import *

import os
import importlib
import datetime

import logging
_logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/token", tags=["auth"], include_in_schema=False)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    def import_auth_module(module_name):
        auth_module = importlib.import_module(module_name)
        return getattr(auth_module, "auth")

    auth = import_auth_module(os.getenv("AUTH_MODULE", "sdmgr.auth.test"))
    await auth(form_data.username, form_data.password)

    _logger.info(f"Providing access token for {form_data.username}.")
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": form_data.username
        }, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

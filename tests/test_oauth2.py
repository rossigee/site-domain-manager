import pytest

from fastapi.security import OAuth2PasswordRequestForm
from fastapi.exceptions import HTTPException

import sdmgr.app


@pytest.mark.asyncio
async def test_oauth2_password_failure():
    form_data = OAuth2PasswordRequestForm("password", "manager", "wrongpass", "test")

    with pytest.raises(HTTPException):
        token = await sdmgr.app.login(form_data)

@pytest.mark.asyncio
async def test_oauth2_token_request():
    form_data = OAuth2PasswordRequestForm("password", "manager", "bigboss", "test")

    token = await sdmgr.app.login(form_data)
    assert isinstance(token['access_token'], bytes)
    assert token['token_type'] == "bearer"

import pytest

from fastapi.security import OAuth2PasswordRequestForm
from starlette.testclient import TestClient

import sdmgr.app
from sdmgr.app import app


async def oauth2_token():
    form_data = OAuth2PasswordRequestForm("password", "testing", "onetwothree", "test")

    token = await sdmgr.app.login(form_data)
    return token['access_token']

@pytest.mark.asyncio
async def test_list_sites_unauthorised():
    with TestClient(app) as client:
        response = client.get("/sites")
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_list_sites():
    token = await oauth2_token()
    with TestClient(app) as client:
        response = client.get("/sites", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        #print(response.json())
        #assert response.json() == {"sites": [...]}

@pytest.mark.asyncio
async def test_check_site_ssl():
    token = await oauth2_token()
    with TestClient(app) as client:
        response = client.get("/sites/1/check/ssl", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        print(response.json())
        assert response.json() == {"sites": []}

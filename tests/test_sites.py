from fastapi import FastAPI
from starlette.testclient import TestClient

from sdmgr.app import app


def oauth2_token():
    with TestClient(app) as client:
        response = client.post("/token", {
            "username": "testing",
            "password": "onetwothree",
            "type": "bearer"
        })
        return response.json()['access_token']


def test_list_sites_unauthorised():
    with TestClient(app) as client:
        response = client.get("/sites")
        assert response.status_code == 401

def test_list_sites():
    token = oauth2_token()
    with TestClient(app) as client:
        response = client.get("/sites", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        #print(response.json())
        #assert response.json() == {"sites": [...]}

def test_check_site_ssl():
    token = oauth2_token()
    with TestClient(app) as client:
        response = client.get("/sites/1/check/ssl", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        print(response.json())
        assert response.json() == {"sites": []}

from fastapi import FastAPI
from starlette.testclient import TestClient

from sdmgr.app import app
client = TestClient(app)


def test_openapi_json():
    response = client.get("/openapi.json")
    assert response.status_code == 200

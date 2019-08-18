from fastapi import HTTPException

async def auth(username, password):
    username_ok = username == "testing"
    password_ok = password == "onetwothree"
    if not username_ok or not password_ok:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

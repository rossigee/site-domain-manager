from fastapi import HTTPException

async def auth(username, password):
    if username == "manager" and password == "bigboss":
        return "manager"
    if username == "admin" and password == "caretaker":
        return "admin"

    raise HTTPException(status_code=400, detail="Incorrect username or password")

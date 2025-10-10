from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

router = APIRouter(prefix="/auth", tags=["auth"])

USERNAME = os.getenv("NEXTAUTH_USERNAME", "admin")
PASSWORD = os.getenv("NEXTAUTH_PASSWORD", "admin")

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(data: LoginRequest):
    if data.username == USERNAME and data.password == PASSWORD:
        return {"access_token": "fake-jwt-token", "username": data.username}
    raise HTTPException(status_code=401, detail="Λάθος στοιχεία σύνδεσης")

@router.post("/register")
def register(data: LoginRequest):
    # εδώ απλά για παράδειγμα (θα μπορούσε να συνδεθεί με DB)
    return {"message": f"Χρήστης {data.username} καταχωρήθηκε επιτυχώς!"}

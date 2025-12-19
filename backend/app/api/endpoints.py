from fastapi import APIRouter
from app.core import safety
from app.opcua import client
import math
import time

router = APIRouter()

# Simple mock state
start_time = time.time()

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

from app.core.auth import authenticate_user
from fastapi import HTTPException

from app.core.auth import authenticate_user
from app.core.users import user_manager
from fastapi import HTTPException
from pydantic import BaseModel

class UserAction(BaseModel):
    username: str
    role: str = "user" # Default if not provided

@router.post("/login")
async def login(creds: LoginRequest):
    # 1. Verify credentials with LDAP
    if authenticate_user(creds.username, creds.password):
        # 2. Check whitelist and get role
        role = user_manager.get_role(creds.username)
        if not role:
             raise HTTPException(status_code=403, detail="Access denied. User not authorized.")
             
        # Return a simple token and role
        return {
            "token": "real-ldap-session-token",
            "username": creds.username,
            "role": role 
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/users")
async def get_users():
    return user_manager.get_users()

@router.post("/users/add")
async def add_user(action: UserAction):
    # Only admins should be able to do this, but for now we trust the UI/Auth flow
    user_manager.add_user(action.username, action.role)
    return {"status": "ok", "users": user_manager.get_users()}

@router.post("/users/update")
async def update_user(action: UserAction):
    user_manager.update_role(action.username, action.role)
    return {"status": "ok", "users": user_manager.get_users()}

@router.post("/users/remove")
async def remove_user(action: UserAction):
    user_manager.remove_user(action.username)
    return {"status": "ok", "users": user_manager.get_users()}

@router.get("/telemetry")
async def get_telemetry():
    # Simulate time "t" as integer steps since server start (similar to frontend behavior)
    # Frontend was approx 1 step every 1.2s.
    elapsed = time.time() - start_time
    x = int(elapsed) # Use seconds as the "time" x-axis
    
    # Generate mock values using the same math as the frontend
    # Note: adjusting frequency to match seconds scale
    # Frontend: sin((x / 6) * PI) where x was incrementing every 1.2s
    # We'll just use x (seconds) directly
    
    data = {
        "time": x,
        "ionV": 4.5 + math.sin((x / 6) * math.pi) * 0.6,
        "ionI": 1.8 + math.cos((x / 8) * math.pi) * 0.4,
        "heatV": 7.0 + math.sin((x / 5) * math.pi) * 0.8,
        "heatI": 3.2 + math.cos((x / 7) * math.pi) * 0.5,
        "heLvl": 68 + math.sin((x / 10) * math.pi) * 6,
        "Thot": 62 + math.sin((x / 9) * math.pi) * 3,
        "Tcold": 28 + math.cos((x / 9) * math.pi) * 3,
    }
    return data

@router.get("/status")
async def get_system_status():
    # Placeholder: fetch status from OPC UA via core logic
    return {"status": "operational", "safety_ok": safety.check_safety_interlocks()}

@router.post("/setpoint")
async def set_parameters(voltage: float):
    # Placeholder: validate and send to OPC UA
    return {"message": f"Setpoint {voltage}V received"}

from fastapi import APIRouter
from app.core import safety
from app.opcua import client
import math
import time

router = APIRouter()

# Simple mock state
start_time = time.time()

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

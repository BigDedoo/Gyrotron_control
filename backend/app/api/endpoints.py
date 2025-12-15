from fastapi import APIRouter
from app.core import safety
from app.opcua import client

router = APIRouter()

@router.get("/status")
async def get_system_status():
    # Placeholder: fetch status from OPC UA via core logic
    return {"status": "operational", "safety_ok": safety.check_safety_interlocks()}

@router.post("/setpoint")
async def set_parameters(voltage: float):
    # Placeholder: validate and send to OPC UA
    return {"message": f"Setpoint {voltage}V received"}

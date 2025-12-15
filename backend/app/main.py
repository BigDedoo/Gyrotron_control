from fastapi import FastAPI
from app.api import endpoints

app = FastAPI(title="Gyrotron Control API")

app.include_router(endpoints.router)

@app.get("/")
async def root():
    return {"message": "Gyrotron Control System API Running"}

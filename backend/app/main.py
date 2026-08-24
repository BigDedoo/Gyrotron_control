from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import endpoints
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(title="Gyrotron Control API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router)


@app.get("/")
async def root():
    return {"message": "Gyrotron Control System API Running"}

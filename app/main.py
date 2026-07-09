# Future FastAPI entry point.
from fastapi import FastAPI
from app.routers import chat, health, models

app = FastAPI()
app.include_router(chat.router)
app.include_router(health.router)
app.include_router(models.router)
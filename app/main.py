from fastapi import FastAPI
from app.routes import health

app = FastAPI(title="Telegram Subscription Platform")

app.include_router(health.router)
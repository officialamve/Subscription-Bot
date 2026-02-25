from fastapi import FastAPI
from app.routes import health
from app.routes import health, creator
from app.routes import health, creator, plan

app = FastAPI(title="Telegram Subscription Platform")

app.include_router(health.router)
app.include_router(creator.router)
app.include_router(plan.router)
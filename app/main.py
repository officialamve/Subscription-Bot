from fastapi import FastAPI
from app.routes import health, creator, plan, payment

app = FastAPI(title="Telegram Subscription Platform")

app.include_router(health.router)
app.include_router(creator.router)
app.include_router(plan.router)
app.include_router(payment.router)
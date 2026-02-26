from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.routes import health, creator, plan, payment
from app.services.expiry_service import remove_expired_subscriptions


# -------------------------
# App Initialization
# -------------------------
app = FastAPI(title="Telegram Subscription Platform")


# -------------------------
# CORS Middleware
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Include Routes
# -------------------------
app.include_router(health.router)
app.include_router(creator.router)
app.include_router(plan.router)
app.include_router(payment.router)


# -------------------------
# Scheduler Setup
# -------------------------
scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def startup_event():
    print("🚀 Application started")
    scheduler.add_job(
        remove_expired_subscriptions,
        trigger="interval",
        minutes=5
    )
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    print("🛑 Application shutting down")
    scheduler.shutdown()
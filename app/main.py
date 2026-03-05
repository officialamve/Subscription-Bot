from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.routes import health, creator, plan, payment, user, subscription
from app.services.subscription_cleanup import remove_expired_subscriptions
from app.scheduler.renewal_reminder import send_renewal_reminders

app = FastAPI(title="Telegram Subscription Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(creator.router)
app.include_router(plan.router)
app.include_router(payment.router)
app.include_router(user.router)
app.include_router(subscription.router)

scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def startup_event():

    print("🚀 Backend started")

    scheduler.add_job(
        remove_expired_subscriptions,
        trigger="interval",
        minutes=10
    )

    scheduler.add_job(
        send_renewal_reminders,
        trigger="interval",
        hours=6
    )

    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
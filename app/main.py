from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import health, creator, plan, payment

app = FastAPI(title="Telegram Subscription Platform")

# CORS Middleware (important for frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for testing only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(health.router)
app.include_router(creator.router)
app.include_router(plan.router)
app.include_router(payment.router)
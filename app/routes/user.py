from fastapi import APIRouter
from app.database import db
from app.services.subscription_service import get_user_subscriptions

router = APIRouter()


@router.get("/users/{telegram_id}/subscriptions")
async def user_subscriptions(telegram_id: int):
    return await get_user_subscriptions(db, telegram_id)
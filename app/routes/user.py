from fastapi import APIRouter, Depends
from database import get_db
from services.subscription_service import get_user_subscriptions

router = APIRouter()

@router.get("/users/{telegram_id}/subscriptions")
async def user_subscriptions(telegram_id: int, db=Depends(get_db)):
    return await get_user_subscriptions(db, telegram_id)
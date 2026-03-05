from fastapi import APIRouter
from app.database import db
from datetime import datetime

router = APIRouter()

@router.get("/users/{telegram_id}/subscriptions")
async def get_user_subscriptions(telegram_id: int):

    subs = db.subscriptions.find({"user_id": telegram_id})

    results = []

    async for sub in subs:

        plan = await db.plans.find_one({"_id": sub["plan_id"]})
        creator = await db.creators.find_one({"_id": sub["creator_id"]})

        now = datetime.utcnow()

        status = "active" if sub["end_date"] > now else "expired"

        results.append({
            "creator_name": creator["name"],
            "plan_name": plan["name"],
            "plan_id": str(plan["_id"]),
            "price": plan["price"],
            "end_date": sub["end_date"],
            "status": status
        })

    return results
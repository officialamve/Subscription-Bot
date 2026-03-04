from fastapi import APIRouter
from bson import ObjectId
from app.database import db

router = APIRouter()


@router.get("/subscriptions/pending/{telegram_id}")
async def check_pending_subscription(telegram_id: int):

    sub = await db.subscriptions.find_one({
        "user_id": telegram_id,
        "is_active": True,
        "invite_sent": False
    })

    if not sub:
        return {"status": "none"}

    creator = await db.creators.find_one({"_id": sub["creator_id"]})

    return {
        "status": "ready",
        "subscription_id": str(sub["_id"]),
        "group_id": creator["group_ids"][0]
    }


@router.put("/subscriptions/{subscription_id}/mark-invite-sent")
async def mark_invite_sent(subscription_id: str):

    await db.subscriptions.update_one(
        {"_id": ObjectId(subscription_id)},
        {"$set": {"invite_sent": True}}
    )

    return {"status": "updated"}
from datetime import datetime
from telegram import Bot
from app.database import db
from app.config import settings


async def remove_expired_subscriptions():

    now = datetime.utcnow()

    expired_subs = db.subscriptions.find({
        "end_date": {"$lt": now},
        "is_active": True
    })

    bot = Bot(token=settings.PLATFORM_BOT_TOKEN)

    async for sub in expired_subs:

        try:

            creator = await db.creators.find_one({"_id": sub["creator_id"]})

            if not creator:
                continue

            group_id = creator["group_ids"][0] if creator.get("group_ids") else None

            if not group_id:
                continue

            await bot.ban_chat_member(group_id, sub["user_id"])
            await bot.unban_chat_member(group_id, sub["user_id"])

            await db.subscriptions.update_one(
                {"_id": sub["_id"]},
                {
                    "$set": {
                        "is_active": False,
                        "status": "expired"
                    }
                }
            )

            print(f"Removed user {sub['user_id']}")

        except Exception as e:
            print("Removal error:", e)
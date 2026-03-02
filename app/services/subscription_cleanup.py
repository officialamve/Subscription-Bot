from datetime import datetime
from telegram import Bot
from bson import ObjectId

from app.database import db
from app.utils.encryption import decrypt_token


async def remove_expired_subscriptions():

    now = datetime.utcnow()

    expired_subs = db.subscriptions.find({
        "end_date": {"$lt": now},
        "is_active": True
    })

    async for sub in expired_subs:

        user_id = sub["user_id"]
        creator_id = sub["creator_id"]

        creator = await db.creators.find_one({"_id": creator_id})

        if not creator:
            continue

        try:
            bot_token = decrypt_token(creator["bot_token_encrypted"])
            bot = Bot(token=bot_token)

            group_id = creator["group_ids"][0]

            # Remove user from group
            await bot.ban_chat_member(group_id, user_id)
            await bot.unban_chat_member(group_id, user_id)

        except Exception as e:
            print("Removal error:", e)
            continue

        # Mark subscription inactive
        await db.subscriptions.update_one(
            {"_id": sub["_id"]},
            {"$set": {"is_active": False}}
        )

        print(f"User {user_id} removed from group {group_id}")
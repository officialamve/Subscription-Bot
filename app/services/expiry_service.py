from datetime import datetime
from telegram import Bot
from app.database import db
from app.utils.encryption import decrypt_token


async def remove_expired_subscriptions():

    now = datetime.utcnow()

    expired_subs = db.subscriptions.find({
        "is_active": True,
        "end_date": {"$lte": now}
    })

    async for sub in expired_subs:

        creator = await db.creators.find_one({"_id": sub["creator_id"]})
        if not creator:
            continue

        token = decrypt_token(creator["bot_token_encrypted"])
        bot = Bot(token=token)

        for group_id in creator["group_ids"]:
            try:
                # Remove user
                await bot.ban_chat_member(
                    chat_id=group_id,
                    user_id=sub["user_id"]
                )

                # Optional: immediately unban so they can rejoin later
                await bot.unban_chat_member(
                    chat_id=group_id,
                    user_id=sub["user_id"]
                )

            except Exception as e:
                print("Telegram removal error:", str(e))

        # Mark subscription inactive
        await db.subscriptions.update_one(
            {"_id": sub["_id"]},
            {"$set": {"is_active": False, "expired_at": now}}
        )

        print(f"User {sub['user_id']} removed due to expiry.")
from datetime import datetime, timedelta
from telegram import Bot

from app.database import db
from app.config import settings


async def send_renewal_reminders():

    now = datetime.utcnow()
    tomorrow = now + timedelta(days=1)

    bot = Bot(token=settings.PLATFORM_BOT_TOKEN)

    subs = db.subscriptions.find({
        "end_date": {"$gte": now, "$lte": tomorrow},
        "is_active": True
    })

    async for sub in subs:

        await bot.send_message(
            chat_id=sub["user_id"],
            text=(
                "⏰ Your subscription expires tomorrow.\n\n"
                "Renew now to keep access."
            )
        )
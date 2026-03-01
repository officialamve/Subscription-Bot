import time
from telegram import Bot
from app.utils.encryption import decrypt_token

async def generate_invite_link(bot_token_encrypted: str, group_id: int):
    bot_token = decrypt_token(bot_token_encrypted)
    bot = Bot(token=bot_token)

    expire_timestamp = int(time.time()) + (48 * 60 * 60)

    invite = await bot.create_chat_invite_link(
        chat_id=group_id,
        member_limit=1,
        expire_date=expire_timestamp
    )

    return invite.invite_link
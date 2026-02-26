from telegram import Bot
from app.utils.encryption import decrypt_token


async def generate_invite_link(bot_token_encrypted, group_id):
    token = decrypt_token(bot_token_encrypted)
    bot = Bot(token=token)

    invite = await bot.create_chat_invite_link(
        chat_id=group_id,
        member_limit=1
    )

    return invite.invite_link
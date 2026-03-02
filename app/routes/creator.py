from fastapi import APIRouter
from datetime import datetime
import secrets

from app.database import db
from app.models.creator_model import CreatorCreate
from app.utils.encryption import encrypt_token

router = APIRouter()


@router.post("/creator/register")
async def register_creator(data: CreatorCreate):

    # Check if creator already exists
    existing = await db.creators.find_one({"telegram_id": data.telegram_id})

    if existing:
        return {
            "message": "Creator already exists",
            "creator_code": existing["creator_code"]
        }

    # Generate unique creator code
    creator_code = secrets.token_hex(4)

    while await db.creators.find_one({"creator_code": creator_code}):
        creator_code = secrets.token_hex(4)

    encrypted_token = encrypt_token(data.bot_token)

    creator_data = {
        "telegram_id": data.telegram_id,
        "name": data.name,
        "creator_code": creator_code,
        "bot_token_encrypted": encrypted_token,
        "group_ids": data.group_ids,
        "created_at": datetime.utcnow(),
        "is_active": True
    }

    await db.creators.insert_one(creator_data)

    return {
        "message": "Creator registered successfully",
        "creator_code": creator_code
    }
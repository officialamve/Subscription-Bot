from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.database import db
from app.models.creator_model import CreatorCreate
from app.utils.encryption import encrypt_token

router = APIRouter()


@router.post("/creator/register")
async def register_creator(data: CreatorCreate):
    existing = await db.creators.find_one({"telegram_id": data.telegram_id})
    if existing:
        raise HTTPException(status_code=400, detail="Creator already exists")

    encrypted_token = encrypt_token(data.bot_token)

    creator_data = {
        "telegram_id": data.telegram_id,
        "name": data.name,
        "bot_token_encrypted": encrypted_token,
        "group_ids": data.group_ids,
        "created_at": datetime.utcnow(),
        "is_active": True
    }

    await db.creators.insert_one(creator_data)

    return {"message": "Creator registered successfully"}
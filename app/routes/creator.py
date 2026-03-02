from fastapi import APIRouter, HTTPException
from datetime import datetime
import secrets

from app.database import db
from app.models.creator_model import CreatorCreate

router = APIRouter()


@router.post("/creator/register")
async def register_creator(data: CreatorCreate):

    existing = await db.creators.find_one({"telegram_id": data.telegram_id})

    if existing:
        return {
            "message": "Creator already exists",
            "creator_code": existing["creator_code"]
        }

    creator_code = secrets.token_hex(4)

    while await db.creators.find_one({"creator_code": creator_code}):
        creator_code = secrets.token_hex(4)

    creator_data = {
        "telegram_id": data.telegram_id,
        "name": data.name,
        "creator_code": creator_code,
        "group_ids": data.group_ids,
        "created_at": datetime.utcnow(),
        "is_active": True
    }

    await db.creators.insert_one(creator_data)

    return {
        "message": "Creator registered successfully",
        "creator_code": creator_code
    }

@router.get("/creator/by-code/{creator_code}")
async def get_creator_by_code(creator_code: str):

    creator = await db.creators.find_one({
        "creator_code": creator_code,
        "is_active": True
    })

    if not creator:
        return None

    return {
        "id": str(creator["_id"]),
        "name": creator["name"]
    }
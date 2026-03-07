from fastapi import APIRouter
from datetime import datetime
from bson import ObjectId
import secrets

from app.database import db
from app.models.creator_model import CreatorCreate

router = APIRouter()


# =====================================================
# REGISTER CREATOR
# =====================================================
@router.post("/creator/register")
async def register_creator(data: CreatorCreate):

    existing = await db.creators.find_one({
        "telegram_id": data.telegram_id
    })

    # If already exists → return existing code
    if existing:
        return {
            "message": "Creator already exists",
            "creator_code": existing["creator_code"]
        }

    # Generate unique creator code
    creator_code = secrets.token_hex(4)

    while await db.creators.find_one({"creator_code": creator_code}):
        creator_code = secrets.token_hex(4)

    creator_data = {
        "telegram_id": data.telegram_id,
        "name": data.name,
        "creator_code": creator_code,
        "group_ids": data.group_ids,
        "group_usernames": data.group_usernames,
        "created_at": datetime.utcnow(),
        "is_active": True
    }

    await db.creators.insert_one(creator_data)

    return {
        "message": "Creator registered successfully",
        "creator_code": creator_code
    }


# =====================================================
# GET CREATOR BY SHARE CODE
# =====================================================
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
        "name": creator.get("name", "Unknown")
    }


# =====================================================
# GET CREATOR BY TELEGRAM ID
# =====================================================
@router.get("/creator/by-telegram/{telegram_id}")
async def get_creator_by_telegram(telegram_id: int):

    creator = await db.creators.find_one({
        "telegram_id": telegram_id,
        "is_active": True
    })

    if not creator:
        return None

    return {
        "id": str(creator["_id"]),
        "name": creator.get("name", "Unknown"),
        "creator_code": creator["creator_code"]
    }


# =====================================================
# CREATOR DASHBOARD STATS
# =====================================================
@router.get("/creator/dashboard/{telegram_id}")
async def creator_dashboard(telegram_id: int):

    creator = await db.creators.find_one({
        "telegram_id": telegram_id,
        "is_active": True
    })

    if not creator:
        return None

    creator_id = creator["_id"]

    plans_count = await db.plans.count_documents({
        "creator_id": creator_id,
        "is_active": True
    })

    now = datetime.utcnow()

    subscribers_count = await db.subscriptions.count_documents({
        "creator_id": creator_id,
        "end_date": {"$gt": now}
    })

    return {
        "name": creator.get("name", "Unknown"),
        "creator_code": creator["creator_code"],
        "group_id": creator["group_ids"][0],
        "plans_count": plans_count,
        "subscribers_count": subscribers_count
    }

@router.get("/creator/{creator_code}/plans-public")
async def public_plans(creator_code: str):

    creator = await db.creators.find_one({
        "creator_code": creator_code,
        "is_active": True
    })

    if not creator:
        return []

    plans = []

    async for plan in db.plans.find({
        "creator_id": creator["_id"],
        "is_active": True
    }):

        plans.append({
            "id": str(plan["_id"]),
            "name": plan["name"],
            "price": plan["price"],
            "duration_days": plan["duration_days"],
            "description": plan.get("description", "")
        })

    return plans
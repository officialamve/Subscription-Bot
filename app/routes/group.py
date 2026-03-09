from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId
from app.database import db
from app.models.group_model import GroupCreate

router = APIRouter()

@router.post("/group")
async def create_group(data: GroupCreate):

    creator = await db.creators.find_one({"_id": ObjectId(data.creator_id)})
    if not creator:
        raise HTTPException(404, "Creator not found")

    existing = await db.groups.find_one({"group_id": data.group_id})
    if existing:
        raise HTTPException(400, "Group already registered")

    group = {
        "creator_id": ObjectId(data.creator_id),
        "group_id": data.group_id,
        "username": data.username,
        "name": data.name,
        "is_public": data.is_public,
        "created_at": datetime.utcnow()
    }

    result = await db.groups.insert_one(group)

    return {
        "id": str(result.inserted_id),
        "group_id": data.group_id,
        "name": data.name
    }
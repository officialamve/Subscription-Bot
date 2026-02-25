from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId
from app.database import db
from app.models.plan_model import PlanCreate

router = APIRouter()


@router.post("/creator/{creator_id}/plan")
async def create_plan(creator_id: str, data: PlanCreate):
    creator = await db.creators.find_one({"_id": ObjectId(creator_id)})

    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    plan_data = {
        "creator_id": ObjectId(creator_id),
        "name": data.name,
        "price": data.price,
        "duration_days": data.duration_days,
        "description": data.description,
        "is_active": True,
        "created_at": datetime.utcnow()
    }

    result = await db.plans.insert_one(plan_data)

    return {
        "message": "Plan created successfully",
        "plan_id": str(result.inserted_id)
    }


@router.get("/creator/{creator_id}/plans")
async def list_plans(creator_id: str):
    plans_cursor = db.plans.find({"creator_id": ObjectId(creator_id), "is_active": True})

    plans = []
    async for plan in plans_cursor:
        plans.append({
            "id": str(plan["_id"]),
            "name": plan["name"],
            "price": plan["price"],
            "duration_days": plan["duration_days"],
            "description": plan.get("description")
        })

    return {"plans": plans}
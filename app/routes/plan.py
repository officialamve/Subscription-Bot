from fastapi import APIRouter, HTTPException
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId

from app.database import db
from app.models.plan_model import PlanCreate

router = APIRouter()


# =========================================================
# HELPER: Validate ObjectId
# =========================================================
def validate_object_id(id_str: str):
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID")


# =========================================================
# CREATE PLAN
# =========================================================
@router.post("/creator/{creator_id}/plan")
async def create_plan(creator_id: str, data: PlanCreate):

    creator_object_id = validate_object_id(creator_id)

    creator = await db.creators.find_one({
        "_id": creator_object_id,
        "is_active": True
    })

    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    plan_data = {
        "creator_id": creator_object_id,
        "name": data.name.strip(),
        "price": data.price,
        "duration_days": data.duration_days,
        "description": data.description.strip() if data.description else "",
        "is_active": True,
        "created_at": datetime.utcnow()
    }

    result = await db.plans.insert_one(plan_data)

    return {
        "plan_id": str(result.inserted_id),
        "name": plan_data["name"],
        "price": plan_data["price"],
        "duration_days": plan_data["duration_days"]
    }

# =========================================================
# GET CREATOR PLANS
# =========================================================
@router.get("/creator/{creator_id}/plans")
async def get_creator_plans(creator_id: str):

    creator_object_id = validate_object_id(creator_id)

    plans = []

    async for plan in db.plans.find({
        "creator_id": creator_object_id,
        "is_active": True
    }).sort("created_at", -1):

        plans.append({
            "id": str(plan["_id"]),
            "name": plan["name"],
            "price": plan["price"],
            "duration_days": plan["duration_days"],
            "description": plan.get("description", "")
        })

    return plans


# =========================================================
# UPDATE PLAN
# =========================================================
@router.put("/plan/{plan_id}")
async def update_plan(plan_id: str, data: dict):

    plan_object_id = validate_object_id(plan_id)

    update_fields = {}

    if "name" in data and isinstance(data["name"], str):
        update_fields["name"] = data["name"].strip()

    if "price" in data and isinstance(data["price"], int):
        update_fields["price"] = data["price"]

    if "duration_days" in data and isinstance(data["duration_days"], int):
        update_fields["duration_days"] = data["duration_days"]

    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    result = await db.plans.update_one(
        {"_id": plan_object_id, "is_active": True},
        {"$set": update_fields}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")

    return {"message": "Plan updated successfully"}


# =========================================================
# PAUSE PLAN
# =========================================================
@router.put("/plan/{plan_id}/pause")
async def pause_plan(plan_id: str):

    plan_object_id = validate_object_id(plan_id)

    result = await db.plans.update_one(
        {"_id": plan_object_id, "is_active": True},
        {"$set": {"is_active": False}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found or already paused")

    return {"message": "Plan paused successfully"}

# =========================================================
# RESUME PLAN
# =========================================================
@router.put("/plan/{plan_id}/resume")
async def resume_plan(plan_id: str):

    plan_object_id = validate_object_id(plan_id)

    result = await db.plans.update_one(
        {"_id": plan_object_id, "is_active": False},
        {"$set": {"is_active": True}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found or already active")

    return {"message": "Plan resumed successfully"}

# =========================================================
# PLAN STATS
# =========================================================
@router.get("/plan/{plan_id}/stats")
async def get_plan_stats(plan_id: str):

    plan_object_id = validate_object_id(plan_id)

    plan = await db.plans.find_one({
        "_id": plan_object_id,
        "is_active": True
    })

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Total subscriptions (lifetime)
    total_subscribers = await db.subscriptions.count_documents({
        "plan_id": plan_object_id
    })

    # Active subscriptions
    active_users = await db.subscriptions.count_documents({
        "plan_id": plan_object_id,
        "is_active": True
    })

    # Total revenue (sum of paid orders)
    pipeline = [
        {
            "$match": {
                "plan_id": plan_object_id,
                "status": "paid"
            }
        },
        {
            "$group": {
                "_id": None,
                "total": {"$sum": "$amount"}
            }
        }
    ]

    revenue_result = await db.orders.aggregate(pipeline).to_list(length=1)
    total_revenue = revenue_result[0]["total"] if revenue_result else 0

    return {
        "name": plan["name"],
        "price": plan["price"],
        "duration_days": plan["duration_days"],
        "description": plan.get("description", ""),
        "total_subscribers": total_subscribers,
        "active_users": active_users,
        "total_revenue": total_revenue
    }
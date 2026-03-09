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
@router.post("/plan")
async def create_plan(data: PlanCreate):

    plan_data = {
        "group_id": ObjectId(data.group_id),
        "name": data.name,
        "price": data.price,
        "duration_days": data.duration_days,
        "description": data.description,
        "max_users": data.max_users,
        "created_at": datetime.utcnow(),
        "is_active": True
    }

    result = await db.plans.insert_one(plan_data)

    return {
        "plan_id": str(result.inserted_id),
        "name": data.name
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
            "description": plan.get("description", ""),
            "max_users": plan.get("max_users", 1)
        })

    return plans


# =========================================================
# UPDATE PLAN
# =========================================================
@router.put("/plan/{plan_id}")
async def update_plan(plan_id: str, data: dict):

    plan_object_id = validate_object_id(plan_id)

    update_fields = {}

    if "name" in data:
        update_fields["name"] = data["name"].strip()

    if "price" in data:
        update_fields["price"] = data["price"]

    if "duration_days" in data:
        update_fields["duration_days"] = data["duration_days"]

    if "description" in data:
        update_fields["description"] = data["description"]

    if "max_users" in data:
        update_fields["max_users"] = data["max_users"]

    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields")

    result = await db.plans.update_one(
        {"_id": plan_object_id},
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

    await db.plans.update_one(
        {"_id": plan_object_id},
        {"$set": {"is_active": False}}
    )

    return {"message": "Plan paused successfully"}


# =========================================================
# RESUME PLAN
# =========================================================
@router.put("/plan/{plan_id}/resume")
async def resume_plan(plan_id: str):

    plan_object_id = validate_object_id(plan_id)

    await db.plans.update_one(
        {"_id": plan_object_id},
        {"$set": {"is_active": True}}
    )

    return {"message": "Plan resumed successfully"}


# =========================================================
# PLAN STATS
# =========================================================
@router.get("/plan/{plan_id}/stats")
async def get_plan_stats(plan_id: str):

    plan_object_id = validate_object_id(plan_id)

    plan = await db.plans.find_one({"_id": plan_object_id})

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    now = datetime.utcnow()

    total_subscribers = await db.subscriptions.count_documents({
        "plan_id": plan_object_id
    })

    active_users = await db.subscriptions.count_documents({
        "plan_id": plan_object_id,
        "end_date": {"$gt": now}
    })

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
        "max_users": plan.get("max_users", 1),
        "total_subscribers": total_subscribers,
        "active_users": active_users,
        "total_revenue": total_revenue
    }
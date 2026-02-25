import razorpay
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from app.database import db
from app.config import settings

router = APIRouter()

razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


@router.post("/payment/create-order")
async def create_order(plan_id: str, user_id: int):

    plan = await db.plans.find_one({"_id": ObjectId(plan_id), "is_active": True})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    amount_paise = plan["price"] * 100

    order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    order_data = {
        "user_id": user_id,
        "plan_id": ObjectId(plan_id),
        "creator_id": plan["creator_id"],
        "razorpay_order_id": order["id"],
        "amount": plan["price"],
        "status": "created",
        "created_at": datetime.utcnow()
    }

    await db.orders.insert_one(order_data)

    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID
    }
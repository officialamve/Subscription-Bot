from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timedelta
from app.database import db
from app.config import settings
import hmac
import hashlib

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

@router.post("/payment/verify")
async def verify_payment(request: Request):

    data = await request.json()

    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        raise HTTPException(status_code=400, detail="Invalid payment data")

    # Verify Signature
    body = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    if expected_signature != razorpay_signature:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # Update order status
    order = await db.orders.find_one({"razorpay_order_id": razorpay_order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    await db.orders.update_one(
        {"razorpay_order_id": razorpay_order_id},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": razorpay_payment_id
        }}
    )

    # Create Subscription
    plan = await db.plans.find_one({"_id": order["plan_id"]})
    expiry_date = datetime.utcnow() + timedelta(days=plan["duration_days"])

    subscription_data = {
        "user_id": order["user_id"],
        "creator_id": order["creator_id"],
        "plan_id": order["plan_id"],
        "start_date": datetime.utcnow(),
        "expiry_date": expiry_date,
        "status": "active"
    }

    await db.subscriptions.insert_one(subscription_data)

    return {"message": "Payment verified and subscription activated"}
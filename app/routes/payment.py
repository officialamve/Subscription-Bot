import razorpay
import hmac
import hashlib

from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timedelta

from app.database import db
from app.config import settings

router = APIRouter()

razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


# -------------------------
# CREATE ORDER
# -------------------------
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


# -------------------------
# VERIFY PAYMENT
# -------------------------
@router.post("/payment/verify")
async def verify_payment(request: Request):

    try:
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid or empty JSON body")

    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        raise HTTPException(status_code=400, detail="Invalid payment data")

    # Generate expected signature
    body = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    if expected_signature != razorpay_signature:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    # Find order
    order = await db.orders.find_one({"razorpay_order_id": razorpay_order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Update order status
    await db.orders.update_one(
        {"razorpay_order_id": razorpay_order_id},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": razorpay_payment_id,
            "paid_at": datetime.utcnow()
        }}
    )

    # Fetch plan
    plan = await db.plans.find_one({"_id": order["plan_id"]})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Create subscription
    expiry_date = datetime.utcnow() + timedelta(days=plan["duration_days"])

    subscription_data = {
        "user_id": order["user_id"],
        "creator_id": order["creator_id"],
        "plan_id": order["plan_id"],
        "start_date": datetime.utcnow(),
        "expiry_date": expiry_date,
        "status": "active",
        "created_at": datetime.utcnow()
    }

    await db.subscriptions.insert_one(subscription_data)

    return {
        "message": "Payment verified and subscription activated"
    }
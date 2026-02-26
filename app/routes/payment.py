import razorpay
import hmac
import hashlib
import requests
import time

from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timedelta

from app.database import db
from app.config import settings

router = APIRouter()

# -------------------------
# Razorpay Client Setup
# -------------------------
session = requests.Session()
session.timeout = 10

razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)
razorpay_client.session = session


# -------------------------
# CREATE ORDER
# -------------------------
@router.post("/payment/create-order")
async def create_order(plan_id: str, user_id: int):

    # Validate ObjectId
    try:
        object_id = ObjectId(plan_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid plan_id")

    plan = await db.plans.find_one({"_id": object_id, "is_active": True})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Reuse existing pending order
    existing_order = await db.orders.find_one({
        "user_id": user_id,
        "plan_id": object_id,
        "status": "created"
    })

    if existing_order:
        return {
            "order_id": existing_order["razorpay_order_id"],
            "amount": existing_order["amount"] * 100,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID
        }

    amount_paise = plan["price"] * 100

    # Retry logic (3 attempts)
    order = None
    for attempt in range(3):
        try:
            order = razorpay_client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "payment_capture": 1
            })
            break
        except Exception as e:
            print(f"Razorpay attempt {attempt + 1} failed:", str(e))
            if attempt == 2:
                raise HTTPException(
                    status_code=500,
                    detail="Payment gateway temporarily unavailable"
                )
            time.sleep(1)

    order_data = {
        "user_id": user_id,
        "plan_id": object_id,
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
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or empty JSON body")

    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        raise HTTPException(status_code=400, detail="Invalid payment data")

    # Verify signature
    body = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    if expected_signature != razorpay_signature:
        raise HTTPException(status_code=400, detail="Payment verification failed")

    order = await db.orders.find_one({"razorpay_order_id": razorpay_order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Prevent duplicate verification
    if order.get("status") == "paid":
        return {"message": "Payment already verified"}

    # Mark order as paid
    await db.orders.update_one(
        {"razorpay_order_id": razorpay_order_id},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": razorpay_payment_id,
            "paid_at": datetime.utcnow()
        }}
    )

    plan = await db.plans.find_one({"_id": order["plan_id"]})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    now = datetime.utcnow()

    # -------------------------
    # EXTEND SUBSCRIPTION LOGIC
    # -------------------------
    existing_subscription = await db.subscriptions.find_one({
        "user_id": order["user_id"],
        "creator_id": order["creator_id"],
        "is_active": True
    })

    if existing_subscription:

        if existing_subscription["end_date"] > now:
            # Extend active subscription
            new_end_date = existing_subscription["end_date"] + timedelta(days=plan["duration_days"])
        else:
            # Restart expired subscription
            new_end_date = now + timedelta(days=plan["duration_days"])

        await db.subscriptions.update_one(
            {"_id": existing_subscription["_id"]},
            {"$set": {
                "end_date": new_end_date,
                "updated_at": now
            }}
        )

        return {"message": "Subscription extended successfully"}

    # Create new subscription
    start_date = now
    end_date = now + timedelta(days=plan["duration_days"])

    subscription_data = {
        "user_id": order["user_id"],
        "creator_id": order["creator_id"],
        "plan_id": order["plan_id"],
        "start_date": start_date,
        "end_date": end_date,
        "is_active": True,
        "created_at": now
    }

    await db.subscriptions.insert_one(subscription_data)

    return {"message": "Payment verified and subscription activated"}
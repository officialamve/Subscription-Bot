import razorpay
import hmac
import hashlib

from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timedelta

from app.database import db
from app.config import settings
from app.utils.telegram import generate_invite_link

router = APIRouter()

# -------------------------
# Razorpay Client Setup
# -------------------------
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


# =========================================================
# CREATE PAYMENT LINK
# =========================================================
@router.post("/payment/create-order")
async def create_payment_link(plan_id: str, user_id: int):

    try:
        object_id = ObjectId(plan_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid plan_id")

    plan = await db.plans.find_one({
        "_id": object_id,
        "is_active": True
    })

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Prevent duplicate unpaid link
    existing = await db.orders.find_one({
        "user_id": user_id,
        "plan_id": object_id,
        "status": "created"
    })

    if existing:
        if "payment_url" in existing:
            return {
                "payment_url": existing["payment_url"]
            }
        else:
            # Old order without payment_url → delete it
            await db.orders.delete_one({"_id": existing["_id"]})

    # Create Razorpay Payment Link
    try:
        payment = razorpay_client.payment_link.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "description": plan["name"],
            "customer": {
                "name": f"Telegram User {user_id}"
            },
            "notify": {
                "sms": False,
                "email": False
            },
            "notes": {
                "user_id": str(user_id),
                "plan_id": str(plan_id),
                "creator_id": str(plan["creator_id"])
            }
        })
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Payment gateway error"
        )

    order_data = {
        "user_id": user_id,
        "plan_id": object_id,
        "creator_id": plan["creator_id"],
        "razorpay_payment_link_id": payment["id"],
        "payment_url": payment["short_url"],
        "amount": plan["price"],
        "status": "created",
        "created_at": datetime.utcnow()
    }

    await db.orders.insert_one(order_data)

    return {
        "payment_url": payment["short_url"]
    }


# =========================================================
# RAZORPAY WEBHOOK (PAYMENT SUCCESS)
# =========================================================
@router.post("/payment/webhook")
async def razorpay_webhook(request: Request):

    body = await request.body()

    signature = request.headers.get("x-razorpay-signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature")

    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event = payload.get("event")

    # We only care about successful payment
    if event != "payment_link.paid":
        return {"message": "Ignored"}

    payment_entity = payload["payload"]["payment_link"]["entity"]

    payment_link_id = payment_entity["id"]
    notes = payment_entity.get("notes", {})

    user_id = int(notes["user_id"])
    plan_id = ObjectId(notes["plan_id"])
    creator_id = ObjectId(notes["creator_id"])

    order = await db.orders.find_one({
        "razorpay_payment_link_id": payment_link_id
    })

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order["status"] == "paid":
        return {"message": "Already processed"}

    # Mark order as paid
    await db.orders.update_one(
        {"_id": order["_id"]},
        {"$set": {
            "status": "paid",
            "paid_at": datetime.utcnow()
        }}
    )

    plan = await db.plans.find_one({"_id": plan_id})
    creator = await db.creators.find_one({"_id": creator_id})

    if not plan or not creator:
        raise HTTPException(status_code=404, detail="Data missing")

    now = datetime.utcnow()

    # -------------------------
    # EXTEND EXISTING SUBSCRIPTION
    # -------------------------
    existing_subscription = await db.subscriptions.find_one({
        "user_id": user_id,
        "creator_id": creator_id,
        "is_active": True
    })

    if existing_subscription:
        if existing_subscription["end_date"] > now:
            new_end_date = existing_subscription["end_date"] + timedelta(days=plan["duration_days"])
        else:
            new_end_date = now + timedelta(days=plan["duration_days"])

        await db.subscriptions.update_one(
            {"_id": existing_subscription["_id"]},
            {"$set": {
                "end_date": new_end_date,
                "updated_at": now
            }}
        )

    else:
        start_date = now
        end_date = now + timedelta(days=plan["duration_days"])

        subscription_data = {
            "user_id": user_id,
            "creator_id": creator_id,
            "plan_id": plan_id,
            "start_date": start_date,
            "end_date": end_date,
            "is_active": True,
            "created_at": now
        }

        await db.subscriptions.insert_one(subscription_data)

    # Generate invite link
    group_id = creator["group_ids"][0]

    invite_link = await generate_invite_link(
        creator["bot_token_encrypted"],
        group_id
    )

    return {
        "message": "Subscription activated",
        "join_link": invite_link
    }
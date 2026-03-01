import razorpay
import hmac
import hashlib

from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timedelta

from telegram import Bot

from app.database import db
from app.config import settings
from app.utils.telegram import generate_invite_link
from app.utils.encryption import decrypt_token

router = APIRouter()

# Razorpay client
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
    except Exception as e:
        print("Razorpay error:", str(e))
        raise HTTPException(status_code=500, detail="Payment gateway error")

    await db.orders.insert_one({
        "user_id": user_id,
        "plan_id": object_id,
        "creator_id": plan["creator_id"],
        "razorpay_payment_link_id": payment["id"],
        "payment_url": payment["short_url"],
        "amount": plan["price"],
        "status": "created",
        "created_at": datetime.utcnow()
    })

    return {"payment_url": payment["short_url"]}


# =========================================================
# WEBHOOK
# =========================================================
@router.post("/payment/webhook")
async def razorpay_webhook(request: Request):

    body = await request.body()
    signature = request.headers.get("x-razorpay-signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    generated_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(generated_signature, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event = payload.get("event")

    # Only handle successful payment link
    if event != "payment_link.paid":
        return {"message": "Ignored"}

    try:
        payment_entity = payload["payload"]["payment_link"]["entity"]
        payment_link_id = payment_entity["id"]
        notes = payment_entity.get("notes", {})

        user_id = int(notes.get("user_id"))
        plan_id = ObjectId(notes.get("plan_id"))
        creator_id = ObjectId(notes.get("creator_id"))

    except Exception as e:
        print("Webhook parsing error:", e)
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    order = await db.orders.find_one({
        "razorpay_payment_link_id": payment_link_id
    })

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Prevent double processing
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

    # ===============================
    # SUBSCRIPTION LOGIC
    # ===============================

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
        await db.subscriptions.insert_one({
            "user_id": user_id,
            "creator_id": creator_id,
            "plan_id": plan_id,
            "start_date": now,
            "end_date": now + timedelta(days=plan["duration_days"]),
            "is_active": True,
            "created_at": now
        })

    # ===============================
    # TELEGRAM MESSAGE SENDING
    # ===============================

    try:
        group_id = creator["group_ids"][0]

        invite_link = await generate_invite_link(
            creator["bot_token_encrypted"],
            group_id
        )

        bot_token = decrypt_token(creator["bot_token_encrypted"])
        bot = Bot(token=bot_token)

        await bot.send_message(
            chat_id=user_id,
            text=f"✅ Payment Successful!\n\nClick below to join your premium group:\n{invite_link}"
        )

    except Exception as e:
        # Do NOT break webhook if Telegram fails
        print("Telegram send error:", e)

    return {"message": "Subscription activated"}
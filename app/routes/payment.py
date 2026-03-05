import razorpay
import hmac
import hashlib

from fastapi import APIRouter, HTTPException, Request
from bson import ObjectId
from datetime import datetime, timedelta

from telegram import Bot

from app.database import db
from app.config import settings

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
    except:
        raise HTTPException(status_code=400, detail="Invalid plan id")

    plan = await db.plans.find_one({
        "_id": object_id,
        "is_active": True
    })

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Razorpay retry (2 attempts)
    payment = None
    for _ in range(2):
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
            break
        except Exception as e:
            print("Razorpay error:", e)

    if not payment:
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

    return {
        "payment_url": payment["short_url"]
    }


# =========================================================
# RAZORPAY WEBHOOK
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

    if payload.get("event") != "payment_link.paid":
        return {"message": "Ignored"}

    entity = payload["payload"]["payment_link"]["entity"]

    payment_link_id = entity["id"]
    notes = entity.get("notes", {})

    user_id = int(notes.get("user_id"))
    plan_id = ObjectId(notes.get("plan_id"))
    creator_id = ObjectId(notes.get("creator_id"))

    order = await db.orders.find_one({
        "razorpay_payment_link_id": payment_link_id
    })

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order["status"] == "paid":
        return {"message": "Already processed"}

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

    # =====================================================
    # CREATE / EXTEND SUBSCRIPTION
    # =====================================================

    existing = await db.subscriptions.find_one({
        "user_id": user_id,
        "creator_id": creator_id,
        "is_active": True
    })

    if existing:

        if existing["end_date"] > now:
            new_end = existing["end_date"] + timedelta(days=plan["duration_days"])
        else:
            new_end = now + timedelta(days=plan["duration_days"])

        await db.subscriptions.update_one(
            {"_id": existing["_id"]},
            {"$set": {"end_date": new_end}}
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

    # =====================================================
    # SEND TELEGRAM INVITE LINK
    # =====================================================

    try:

        bot = Bot(token=settings.PLATFORM_BOT_TOKEN)

        group_id = creator["group_ids"][0]

        invite_link = await bot.create_chat_invite_link(
            chat_id=group_id,
            member_limit=plan.get("max_users", 1)
            expire_date=int((datetime.utcnow() + timedelta(hours=48)).timestamp())
        )

        await bot.send_message(
            chat_id=user_id,
            text=(
                "✅ Payment Successful!\n\n"
                "Click below to join your premium group:\n\n"
                f"{invite_link.invite_link}\n\n"
                "⚠️ Link valid for 48 hours and 1 use only."
            )
        )

    except Exception as e:
        import traceback
        print("TELEGRAM ERROR OCCURRED")
        traceback.print_exc()

    return {"message": "Subscription activated"}
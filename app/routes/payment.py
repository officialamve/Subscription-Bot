from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from bson import ObjectId
import razorpay

from app.database import db
from app.config import settings
from telegram import Bot

router = APIRouter()

razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


# =========================================================
# CREATE PAYMENT ORDER
# =========================================================

@router.post("/payment/create-order")
async def create_order(user_id: int, plan_id: str):

    plan = await db.plans.find_one({"_id": ObjectId(plan_id)})

    if not plan:
        raise HTTPException(404, "Plan not found")

    # =========================
    # PLAN LIMIT CHECK
    # =========================

    if plan["max_users"] > 0:

        active_users = await db.subscriptions.count_documents({
            "plan_id": plan["_id"],
            "end_date": {"$gt": datetime.utcnow()}
        })

        if active_users >= plan["max_users"]:
            raise HTTPException(400, "Plan is full")

    # =========================
    # CREATE PAYMENT LINK
    # =========================

    try:

        payment = razorpay_client.payment_link.create({
            "amount": plan["price"] * 100,
            "currency": "INR",
            "description": f"{plan['name']} Subscription",
            "notify": {"sms": False, "email": False}
        })

    except Exception as e:
        print("Razorpay error:", e)
        raise HTTPException(500, "Payment provider error")

    order_data = {
        "user_id": user_id,
        "plan_id": plan["_id"],
        "creator_id": plan["creator_id"],
        "amount": plan["price"],
        "razorpay_payment_link_id": payment["id"],
        "payment_url": payment["short_url"],
        "status": "pending",
        "created_at": datetime.utcnow()
    }

    await db.orders.insert_one(order_data)

    return {
        "payment_url": payment["short_url"]
    }


# =========================================================
# RAZORPAY WEBHOOK
# =========================================================

@router.post("/payment/webhook")
async def razorpay_webhook(payload: dict):

    payment_link_id = payload.get("payload", {}).get("payment_link", {}).get("entity", {}).get("id")

    if not payment_link_id:
        return {"status": "ignored"}

    order = await db.orders.find_one({
        "razorpay_payment_link_id": payment_link_id
    })

    if not order:
        return {"status": "not_found"}

    if order["status"] == "paid":
        return {"status": "already_processed"}

    await db.orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"status": "paid", "paid_at": datetime.utcnow()}}
    )

    # =========================
    # CREATE SUBSCRIPTION
    # =========================

    plan = await db.plans.find_one({"_id": order["plan_id"]})

    start = datetime.utcnow()
    end = start + timedelta(days=plan["duration_days"])

    subscription_data = {
        "user_id": order["user_id"],
        "creator_id": order["creator_id"],
        "plan_id": order["plan_id"],
        "start_date": start,
        "end_date": end,
        "is_active": True,
        "created_at": datetime.utcnow()
    }

    result = await db.subscriptions.insert_one(subscription_data)

    # =========================
    # SEND INVITE LINK
    # =========================

    creator = await db.creators.find_one({"_id": order["creator_id"]})

    group_id = creator["group_ids"][0]

    bot = Bot(token=settings.PLATFORM_BOT_TOKEN)

    invite_link = await bot.create_chat_invite_link(
        chat_id=group_id,
        member_limit=1,
        expire_date=int((datetime.utcnow() + timedelta(hours=48)).timestamp())
    )

    await bot.send_message(
        chat_id=order["user_id"],
        text=(
            "✅ Payment Successful!\n\n"
            "Click below to join your premium group:\n"
            f"{invite_link.invite_link}\n\n"
            "⚠️ Link valid for 48 hours."
        )
    )

    return {"status": "ok"}
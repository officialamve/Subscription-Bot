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

    max_users = plan.get("max_users", 0)

    if max_users > 0:

        active_users = await db.subscriptions.count_documents({
            "plan_id": plan["_id"],
            "end_date": {"$gt": datetime.utcnow()}
        })

        if active_users >= max_users:
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

    payment_link_id = payload.get(
        "payload", {}
    ).get(
        "payment_link", {}
    ).get(
        "entity", {}
    ).get(
        "id"
    )

    if not payment_link_id:
        return {"status": "ignored"}

    # =========================
    # ATOMIC UPDATE (PREVENT DUPLICATE WEBHOOK)
    # =========================

    order = await db.orders.find_one_and_update(
        {
            "razorpay_payment_link_id": payment_link_id,
            "status": "pending"
        },
        {
            "$set": {
                "status": "paid",
                "paid_at": datetime.utcnow()
            }
        }
    )

    if not order:
        return {"status": "already_processed"}

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

    await db.subscriptions.insert_one(subscription_data)

    # =========================
    # SEND ACCESS MESSAGE
    # =========================

    creator = await db.creators.find_one({"_id": order["creator_id"]})

    bot = Bot(token=settings.PLATFORM_BOT_TOKEN)

    await bot.send_message(
        chat_id=order["user_id"],
        text=(
            "✅ <b>Payment Successful!</b>\n\n"
            "Click below to request access to the premium group:\n\n"
            f"https://t.me/{creator['group_username']}\n\n"
            "Your request will be automatically approved."
        ),
        parse_mode="HTML"
    )

    return {"status": "ok"}
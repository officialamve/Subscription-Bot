from datetime import datetime
from bson import ObjectId

async def get_user_subscriptions(db, telegram_id: int):
    now = datetime.utcnow()

    pipeline = [
        {"$match": {"user_id": telegram_id}},
        {
            "$lookup": {
                "from": "plans",
                "localField": "plan_id",
                "foreignField": "_id",
                "as": "plan"
            }
        },
        {"$unwind": "$plan"},
        {
            "$lookup": {
                "from": "creators",
                "localField": "creator_id",
                "foreignField": "_id",
                "as": "creator"
            }
        },
        {"$unwind": "$creator"},
        {
            "$project": {
                "_id": 0,
                "creator_name": "$creator.name",
                "plan_name": "$plan.name",
                "price": "$plan.price",
                "end_date": 1,
                "status": 1
            }
        }
    ]

    data = []
    async for sub in db.subscriptions.aggregate(pipeline):
        end_date = sub["end_date"]
        days_remaining = (end_date - now).days

        sub["days_remaining"] = max(days_remaining, 0)
        sub["status"] = "active" if end_date > now else "expired"

        data.append(sub)

    return data
from pydantic import BaseModel
from typing import Optional


class PlanCreate(BaseModel):
    name: str
    price: int
    duration_days: int
    description: Optional[str] = ""
    max_users: int = 0  # 0 = unlimited users
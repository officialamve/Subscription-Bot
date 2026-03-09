from pydantic import BaseModel
from typing import Optional

class PlanCreate(BaseModel):
    group_id: str
    name: str
    price: int
    duration_days: int
    description: Optional[str] = ""
    max_users: int = 0
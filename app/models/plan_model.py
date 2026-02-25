from pydantic import BaseModel
from typing import Optional


class PlanCreate(BaseModel):
    name: str
    price: int  # INR in rupees
    duration_days: int
    description: Optional[str] = None
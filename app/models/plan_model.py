from pydantic import BaseModel, Field
from typing import Optional

class PlanCreate(BaseModel):
    name: str = Field(..., min_length=1)
    price: int
    duration_days: int
    description: Optional[str] = ""
from pydantic import BaseModel
from typing import List


class CreatorCreate(BaseModel):
    telegram_id: int
    name: str
    group_ids: List[int]
    group_username: str
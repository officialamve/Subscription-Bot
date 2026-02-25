from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class CreatorCreate(BaseModel):
    telegram_id: int
    name: str
    bot_token: str
    group_ids: List[int]


class CreatorDB(BaseModel):
    telegram_id: int
    name: str
    bot_token_encrypted: str
    group_ids: List[int]
    created_at: datetime
    is_active: bool = True
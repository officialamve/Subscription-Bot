from pydantic import BaseModel
from typing import Optional

class GroupCreate(BaseModel):
    creator_id: str
    group_id: int
    name: str
    is_public: bool
    username: Optional[str] = None
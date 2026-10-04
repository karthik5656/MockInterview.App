from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class QuestionRead(BaseModel):
    id: UUID
    session_id: UUID
    idx: int
    text: str
    created_at: datetime

    class Config:
        from_attributes = True
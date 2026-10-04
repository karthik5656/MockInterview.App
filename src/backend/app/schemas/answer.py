from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel
from app.schemas.session import QuestionBrief


class AnswerSubmitResponse(BaseModel):
    answer_id: UUID
    transcript: str
    next_question: Optional[QuestionBrief] = None
    done: bool


class AnswerRetryResponse(BaseModel):
    answer_id: UUID
    status: Literal["pending"]
    message: str
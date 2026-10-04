from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    resume_text: str = Field(..., min_length=1)
    jd_text: str = Field(..., min_length=1)
    difficulty: Literal["junior", "mid", "senior", "staff"] = "senior"
    include_topics: List[str] = Field(default_factory=list)
    exclude_topics: List[str] = Field(default_factory=list)
    max_questions: int = Field(default=10, ge=1, le=20)


class QuestionBrief(BaseModel):
    id: UUID
    index: int
    text: str


class SessionCreateResponse(BaseModel):
    session_id: UUID
    question: QuestionBrief


class SessionEndResponse(BaseModel):
    status: Literal["ended"]
    pending_evaluations: int
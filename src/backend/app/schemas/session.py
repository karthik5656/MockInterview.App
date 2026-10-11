from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    resume_text: str = Field(..., min_length=50, description="Candidate resume text (min 50 characters)")
    jd_text: str = Field(..., min_length=50, description="Job description text (min 50 characters)")
    difficulty: Literal["junior", "mid", "senior", "staff"] = Field(
        default="senior", description="Target interview difficulty level"
    )
    include_topics: List[str] = Field(
        default_factory=list, description="Mandatory topics to be covered"
    )
    exclude_topics: List[str] = Field(
        default_factory=list, description="Topics to strictly avoid"
    )
    max_questions: int = Field(
        default=10, ge=1, le=20, description="Total number of interview questions (1 to 20)"
    )


class QuestionBrief(BaseModel):
    id: UUID
    index: int
    text: str


class SessionCreateResponse(BaseModel):
    session_id: UUID
    question: QuestionBrief


class SessionEndResponse(BaseModel):
    status: Literal["ended"] = "ended"
    pending_evaluations: int
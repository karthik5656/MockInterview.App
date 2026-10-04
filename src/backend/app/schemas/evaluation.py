from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class StarScore(BaseModel):
    situation: int = Field(ge=0, le=3)
    task: int = Field(ge=0, le=2)
    action: int = Field(ge=0, le=3)
    result: int = Field(ge=0, le=2)
    notes: str


class TechnicalDepth(BaseModel):
    score: int = Field(ge=0, le=10)
    notes: str


class EvaluationResult(BaseModel):
    score: int = Field(ge=0, le=10)
    star: StarScore
    technical_depth: TechnicalDepth
    missing_points: List[str] = Field(default_factory=list)
    suggested_answer: str


class ResultItem(BaseModel):
    question: str
    transcript: str
    status: Literal["pending", "evaluated", "failed"]
    evaluation: Optional[EvaluationResult] = None


class ProgressStatus(BaseModel):
    total: int
    evaluated: int
    failed: int


class ResultsResponse(BaseModel):
    status: Literal["in_progress", "ended"]
    progress: ProgressStatus
    overall_score: Optional[float] = None
    items: List[ResultItem]
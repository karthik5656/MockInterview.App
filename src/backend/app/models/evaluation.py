import uuid
from datetime import datetime
from typing import List
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("answers.id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    star: Mapped[dict] = mapped_column(JSONB, nullable=False)
    technical_depth: Mapped[dict] = mapped_column(JSONB, nullable=False)
    missing_points: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    suggested_answer: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    answer = relationship("Answer", back_populates="evaluation")
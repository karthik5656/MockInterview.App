import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Text, Integer, Numeric, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def _generate_uuid() -> uuid.UUID:
    return getattr(uuid, "uuid7", uuid.uuid4)()


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_generate_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    include_topics: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    exclude_topics: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    max_questions: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    overall_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 1), nullable=True)

    questions = relationship("Question", back_populates="session", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="session", cascade="all, delete-orphan")
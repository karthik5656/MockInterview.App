import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import BadInputException, ConflictException, NotFoundException
from app.core.database import get_db
from app.core.logging import logger
from app.models.answer import Answer
from app.models.question import Question
from app.models.session import Session
from app.schemas.session import (
    QuestionBrief,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionEndResponse,
)
from app.services.document_parser import DocumentParser
from app.services.question_generator import question_generator

router = APIRouter()

ALLOWED_DIFFICULTIES = {"junior", "mid", "senior", "staff"}


def _parse_topics_input(topics: Optional[str]) -> List[str]:
    """Helper to parse topics from form data (JSON list or comma-separated)."""
    if not topics:
        return []
    stripped = topics.strip()
    if not stripped:
        return []
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(t).strip() for t in parsed if str(t).strip()]
        except json.JSONDecodeError:
            pass
    return [t.strip() for t in stripped.split(",") if t.strip()]


async def _create_session_with_first_question(
    db: AsyncSession,
    resume_text: str,
    jd_text: str,
    difficulty: str,
    include_topics: List[str],
    exclude_topics: List[str],
    max_questions: int,
) -> SessionCreateResponse:
    # 1. Validation
    difficulty_lower = difficulty.lower().strip()
    if difficulty_lower not in ALLOWED_DIFFICULTIES:
        raise BadInputException(
            f"Invalid difficulty '{difficulty}'. Must be one of: {', '.join(sorted(ALLOWED_DIFFICULTIES))}"
        )

    if max_questions < 1 or max_questions > 20:
        raise BadInputException("max_questions must be between 1 and 20")

    if len(resume_text.strip()) < 50:
        raise BadInputException("resume_text must be at least 50 characters")

    if len(jd_text.strip()) < 50:
        raise BadInputException("jd_text must be at least 50 characters")

    # Clean & truncate texts for storage
    clean_resume = DocumentParser.truncate_resume(resume_text)
    clean_jd = DocumentParser.truncate_jd(jd_text)

    # 2. Insert session
    session_obj = Session(
        resume_text=clean_resume,
        jd_text=clean_jd,
        difficulty=difficulty_lower,
        include_topics=include_topics,
        exclude_topics=exclude_topics,
        max_questions=max_questions,
    )
    db.add(session_obj)
    await db.flush()

    # 3. Generate Question 1
    question_text = await question_generator.generate_question(
        difficulty=difficulty_lower,
        resume_text=clean_resume,
        jd_text=clean_jd,
        include_topics=include_topics,
        exclude_topics=exclude_topics,
        question_index=1,
        max_questions=max_questions,
        prior_interactions=[],
    )

    # 4. Insert Question 1
    question_obj = Question(
        session_id=session_obj.id,
        idx=1,
        text=question_text,
    )
    db.add(question_obj)
    await db.commit()
    await db.refresh(session_obj)
    await db.refresh(question_obj)

    logger.info(
        "Successfully created session %s with Question 1 (id: %s)",
        session_obj.id,
        question_obj.id,
    )

    return SessionCreateResponse(
        session_id=session_obj.id,
        question=QuestionBrief(
            id=question_obj.id,
            index=question_obj.idx,
            text=question_obj.text,
        ),
    )


@router.post(
    "",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize interview session and generate first question",
)
async def create_session(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionCreateResponse:
    """Creates a new interview session using raw text payloads and generates the first question."""
    return await _create_session_with_first_question(
        db=db,
        resume_text=payload.resume_text,
        jd_text=payload.jd_text,
        difficulty=payload.difficulty,
        include_topics=payload.include_topics,
        exclude_topics=payload.exclude_topics,
        max_questions=payload.max_questions,
    )


@router.post(
    "/upload",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize interview session from uploaded resume and JD documents",
)
async def create_session_from_upload(
    resume_file: UploadFile = File(..., description="Resume file (PDF, DOCX, or TXT)"),
    jd_file: UploadFile = File(..., description="Job Description file (PDF, DOCX, or TXT)"),
    difficulty: str = Form("senior"),
    include_topics: Optional[str] = Form(None),
    exclude_topics: Optional[str] = Form(None),
    max_questions: int = Form(10),
    db: AsyncSession = Depends(get_db),
) -> SessionCreateResponse:
    """Parses uploaded resume and job description documents and initializes the interview session."""
    resume_text = await DocumentParser.parse_upload_file(resume_file)
    jd_text = await DocumentParser.parse_upload_file(jd_file)

    parsed_include = _parse_topics_input(include_topics)
    parsed_exclude = _parse_topics_input(exclude_topics)

    return await _create_session_with_first_question(
        db=db,
        resume_text=resume_text,
        jd_text=jd_text,
        difficulty=difficulty,
        include_topics=parsed_include,
        exclude_topics=parsed_exclude,
        max_questions=max_questions,
    )


@router.post(
    "/{id}/end",
    response_model=SessionEndResponse,
    status_code=status.HTTP_200_OK,
    summary="End an active interview session",
)
async def end_session(
    id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionEndResponse:
    """Terminates an interview session early or on completion.

    Sets ended_at timestamp and returns count of pending evaluations.
    """
    # 1. Fetch session
    result = await db.execute(select(Session).where(Session.id == id))
    session_obj = result.scalar_one_or_none()

    if session_obj is None:
        raise NotFoundException(f"Session with ID '{id}' was not found.")

    # 2. Check if already ended
    if session_obj.ended_at is not None:
        raise ConflictException("Session already ended")

    # 3. Set ended_at
    session_obj.ended_at = datetime.now(timezone.utc)

    # 4. Count pending evaluations for this session
    pending_query = select(func.count(Answer.id)).where(
        Answer.session_id == id,
        Answer.status == "pending",
    )
    pending_count_res = await db.execute(pending_query)
    pending_count = pending_count_res.scalar_one() or 0

    await db.commit()
    logger.info("Session %s ended with %d pending evaluations", id, pending_count)

    return SessionEndResponse(
        status="ended",
        pending_evaluations=pending_count,
    )
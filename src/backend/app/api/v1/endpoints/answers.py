import os
import tempfile
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.errors import (
    AppException,
    BadInputException,
    ConflictException,
    NotFoundException,
)
from app.core.database import get_db
from app.core.logging import logger
from app.models.answer import Answer
from app.models.question import Question
from app.models.session import Session
from app.schemas.answer import AnswerSubmitResponse
from app.schemas.session import QuestionBrief
from app.services.keyword_extractor import keyword_extractor
from app.services.question_generator import question_generator
from app.services.queue_service import queue_service
from app.services.transcription_service import transcription_service

router = APIRouter()

MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
}

EXTENSION_MAP = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mp4": ".mp4",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
}


def _extract_base_mime(content_type: Optional[str]) -> str:
    if not content_type:
        return ""
    return content_type.split(";")[0].strip().lower()


@router.post(
    "/sessions/{id}/answers",
    response_model=AnswerSubmitResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit an answer via voice audio or text fallback",
)
async def submit_answer(
    id: UUID,
    question_id: UUID = Form(..., description="ID of the question being answered"),
    audio: Optional[UploadFile] = File(None, description="Recorded audio blob"),
    text_fallback: Optional[str] = Form(None, description="Optional text fallback response"),
    db: AsyncSession = Depends(get_db),
) -> AnswerSubmitResponse:
    """Ingests audio or text response, executes transcription with jargon seeding,

    persists the answer, dispatches evaluation job, and advances the session.
    """
    # 1. Validate session exists and is active
    session_res = await db.execute(select(Session).where(Session.id == id))
    session_obj = session_res.scalar_one_or_none()

    if session_obj is None:
        raise NotFoundException(f"Session with ID '{id}' was not found.")

    if session_obj.ended_at is not None:
        raise ConflictException("Session has already ended.")

    # 2. Validate question belongs to session and has no answer
    question_res = await db.execute(
        select(Question)
        .options(selectinload(Question.answer))
        .where(Question.id == question_id, Question.session_id == id)
    )
    question_obj = question_res.scalar_one_or_none()

    if question_obj is None:
        raise NotFoundException(f"Question with ID '{question_id}' was not found for this session.")

    if question_obj.answer is not None:
        raise ConflictException("Question has already been answered.")

    # 3. Process Audio or Text Fallback
    transcript = ""
    audio_seconds = 0.0

    has_audio = audio is not None and bool(audio.filename or audio.size)
    has_text = text_fallback is not None and bool(text_fallback.strip())

    if not has_audio and not has_text:
        raise BadInputException("Either audio or text_fallback must be provided.")

    if has_audio and audio is not None:
        # Validate MIME type
        base_mime = _extract_base_mime(audio.content_type)
        if base_mime not in SUPPORTED_AUDIO_MIME_TYPES:
            raise AppException(
                code="UNSUPPORTED_MEDIA_TYPE",
                message="Unsupported media type. Supported formats: audio/webm, audio/ogg, audio/wav, audio/mp4, audio/x-m4a.",
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        # Stream audio and enforce 10 MB payload limit
        file_suffix = EXTENSION_MAP.get(base_mime, ".webm")
        temp_file = tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False)
        temp_path = temp_file.name
        total_bytes = 0

        try:
            while True:
                chunk = await audio.read(1024 * 64)  # 64KB chunks
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > MAX_AUDIO_SIZE_BYTES:
                    temp_file.close()
                    raise AppException(
                        code="PAYLOAD_TOO_LARGE",
                        message="Audio file exceeds maximum size of 10 MB.",
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
                temp_file.write(chunk)
            temp_file.flush()
            temp_file.close()

            if total_bytes == 0:
                raise AppException(
                    code="EMPTY_AUDIO",
                    message="No speech detected in audio. Please check your microphone and try again.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Domain jargon prompt seeding from Resume & JD
            seeded_jargon = keyword_extractor.extract_keywords(
                resume_text=session_obj.resume_text,
                jd_text=session_obj.jd_text,
            )

            # Transcribe with faster-whisper (CPU int8 in background thread)
            transcript, audio_seconds = await transcription_service.transcribe(
                audio_file_path=temp_path,
                initial_prompt=seeded_jargon,
            )

        finally:
            # Strict Privacy Rule: Clean up ephemeral audio file immediately
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    elif has_text and text_fallback is not None:
        transcript = text_fallback.strip()
        audio_seconds = 0.0

    # 4. Check for Empty / Silent Audio
    if transcription_service.is_silent_or_empty(transcript):
        raise AppException(
            code="EMPTY_AUDIO",
            message="No speech detected in audio. Please check your microphone and try again.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 5. Insert Answer Row into Database
    answer_obj = Answer(
        question_id=question_obj.id,
        session_id=session_obj.id,
        transcript=transcript,
        audio_seconds=audio_seconds,
        status="pending",
        attempts=0,
    )
    db.add(answer_obj)
    await db.flush()

    # Link answer in memory for subsequent question context
    question_obj.answer = answer_obj

    # 6. Check question limit and determine next step
    total_answers_res = await db.execute(
        select(func.count(Answer.id)).where(Answer.session_id == session_obj.id)
    )
    answered_count = total_answers_res.scalar_one() or 1

    next_question_brief: Optional[QuestionBrief] = None
    done: bool = False

    if answered_count >= session_obj.max_questions:
        session_obj.ended_at = datetime.now(timezone.utc)
        done = True
        next_question_brief = None
    else:
        # Load all prior questions with answers for context
        all_questions_res = await db.execute(
            select(Question)
            .options(selectinload(Question.answer))
            .where(Question.session_id == session_obj.id)
            .order_by(Question.idx.asc())
        )
        all_questions = all_questions_res.scalars().all()

        prior_interactions = [
            {
                "index": q.idx,
                "question": q.text,
                "answer_summary": (q.answer.transcript if q.answer else "")[:300],
            }
            for q in all_questions
        ]

        next_idx = len(all_questions) + 1
        next_question_text = await question_generator.generate_question(
            difficulty=session_obj.difficulty,
            resume_text=session_obj.resume_text,
            jd_text=session_obj.jd_text,
            include_topics=session_obj.include_topics,
            exclude_topics=session_obj.exclude_topics,
            question_index=next_idx,
            max_questions=session_obj.max_questions,
            prior_interactions=prior_interactions,
        )

        next_q_obj = Question(
            session_id=session_obj.id,
            idx=next_idx,
            text=next_question_text,
        )
        db.add(next_q_obj)
        await db.flush()

        next_question_brief = QuestionBrief(
            id=next_q_obj.id,
            index=next_q_obj.idx,
            text=next_q_obj.text,
        )
        done = False

    # 7. Enqueue evaluation message to Azure Storage Queue
    queue_service.send_evaluation_message(
        answer_id=str(answer_obj.id),
        session_id=str(session_obj.id),
        attempt=1,
    )

    # 8. Commit DB transaction
    await db.commit()
    await db.refresh(answer_obj)

    logger.info(
        "Answer %s submitted successfully for session %s (done=%s)",
        answer_obj.id,
        session_obj.id,
        done,
    )

    return AnswerSubmitResponse(
        answer_id=answer_obj.id,
        transcript=answer_obj.transcript,
        next_question=next_question_brief,
        done=done,
    )

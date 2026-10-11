import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from openai import AsyncAzureOpenAI, AsyncOpenAI, APIConnectionError, RateLimitError, APITimeoutError, InternalServerError

from app.core.config import settings
from app.core.logging import logger
from app.api.errors import AppException
from app.services.document_parser import DocumentParser


class QuestionGenerator:
    """Service to generate dynamic interview questions using Azure OpenAI / Azure AI Foundry."""

    def __init__(self):
        self._client: Optional[Union[AsyncAzureOpenAI, AsyncOpenAI]] = None

    def _get_client(self) -> Union[AsyncAzureOpenAI, AsyncOpenAI]:
        if self._client is None:
            raw_endpoint = (settings.AZURE_OPENAI_ENDPOINT or "").strip()
            endpoint = raw_endpoint.rstrip("/")

            # Check if this is an Azure AI Foundry services endpoint (v1 REST API)
            if "services.ai.azure.com" in endpoint or endpoint.endswith("/v1") or "/openai/v1" in endpoint:
                base_url = endpoint if endpoint.endswith("/v1") else f"{endpoint}/openai/v1"
                logger.info("Initializing AsyncOpenAI client for Azure AI Foundry endpoint: %s", base_url)
                self._client = AsyncOpenAI(
                    base_url=base_url,
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    default_headers={"api-key": settings.AZURE_OPENAI_API_KEY},
                )
            else:
                logger.info("Initializing AsyncAzureOpenAI client for endpoint: %s", endpoint)
                self._client = AsyncAzureOpenAI(
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    azure_endpoint=endpoint,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                )
        return self._client

    def _is_placeholder_config(self) -> bool:
        key = (settings.AZURE_OPENAI_API_KEY or "").lower()
        endpoint = (settings.AZURE_OPENAI_ENDPOINT or "").lower()
        return (
            not key
            or "your-azure" in key
            or "dummy" in key
            or "placeholder" in key
            or not endpoint
            or "your-resource" in endpoint
        )

    def _generate_fallback_question(
        self,
        difficulty: str,
        include_topics: List[str],
        question_index: int,
    ) -> str:
        """Fallback question generator when Azure OpenAI is in placeholder/mock mode."""
        primary_topic = include_topics[0] if include_topics else "software architecture"
        if question_index == 1:
            return (
                f"To kick off our {difficulty}-level interview, could you walk me through a complex "
                f"project from your recent experience where you worked on {primary_topic}, and detail "
                f"the architectural trade-offs you had to make?"
            )
        else:
            return (
                f"Building on our discussion around {primary_topic}, how did you approach observability, "
                f"error handling, and scalability in that system as load increased?"
            )

    def _build_system_prompt(
        self,
        difficulty: str,
        include_topics: List[str],
        exclude_topics: List[str],
    ) -> str:
        topics_include_str = ", ".join(include_topics) if include_topics else "General core requirements from JD"
        topics_exclude_str = ", ".join(exclude_topics) if exclude_topics else "None"

        return f"""You are a Senior Technical Interviewer conducting a realistic technical interview.
Your role, depth, and questioning style must be calibrated to the specified difficulty level: '{difficulty}' (junior, mid, senior, staff).

Strict Interview Rules:
1. Candidate Alignment: Anchor questions firmly in the intersection of the candidate's Resume and the Job Description.
2. Mandatory Coverage: Prioritize and adhere to include_topics: [{topics_include_str}].
3. Strict Avoidance: You MUST NEVER ask about, mention, or touch upon any topic in exclude_topics: [{topics_exclude_str}].
4. Question 1 (First Question): Must start with an introductory or foundational role-relevant challenge tailored to the resume background.
5. Subsequent Questions: Branch dynamically: either follow up on candidate's prior answer depth, or pivot to an uncovered JD requirement.
6. Repetition Guard: Never repeat a previously asked question or dwell on already answered technical facets.
7. Tone & Brevity: Keep the question direct, realistic, and focused on technical depth. Avoid fluff or preamble like 'Welcome to the interview'.
8. JSON Output: You must respond ONLY with a valid JSON object matching:
{{
  "question_text": "<single concise interview question>"
}}
"""

    async def generate_question(
        self,
        difficulty: str,
        resume_text: str,
        jd_text: str,
        include_topics: List[str],
        exclude_topics: List[str],
        question_index: int = 1,
        max_questions: int = 10,
        prior_interactions: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generates an interview question using Azure OpenAI gpt-4o-mini with retries."""
        # 1. Truncate text according to token budget guards
        truncated_resume = DocumentParser.truncate_resume(resume_text)
        truncated_jd = DocumentParser.truncate_jd(jd_text)

        # 2. Check for placeholder environment in local development
        # if self._is_placeholder_config():
        #     logger.warning(
        #         "Azure OpenAI credentials are placeholders. Using simulated contextual question generator."
        #     )
        #     return self._generate_fallback_question(difficulty, include_topics, question_index)

        # 3. Assemble prompt context schema
        context_payload = {
            "difficulty": difficulty,
            "resume": truncated_resume,
            "job_description": truncated_jd,
            "include_topics": include_topics,
            "exclude_topics": exclude_topics,
            "question_index": question_index,
            "max_questions": max_questions,
            "prior_interactions": prior_interactions or [],
        }

        system_prompt = self._build_system_prompt(difficulty, include_topics, exclude_topics)
        user_prompt = json.dumps(context_payload, indent=2)

        client = self._get_client()
        max_attempts = 3
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "Calling Azure OpenAI gpt-4o-mini for question generation (attempt %d/%d, question_index=%d)",
                    attempt,
                    max_attempts,
                    question_index,
                )
                response = await client.chat.completions.create(
                    model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"},
                    timeout=10.0,
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Received empty response content from LLM")

                parsed = json.loads(content)
                question_text = parsed.get("question_text", "").strip()

                if not question_text:
                    raise ValueError("Response JSON missing 'question_text' field")

                # Validate exclude_topics are not in the question text
                # violates_excluded = any(
                #     ex.strip().lower() in question_text.lower()
                #     for ex in exclude_topics
                #     if ex.strip()
                # )
                # if violates_excluded and attempt < max_attempts:
                #     logger.warning(
                #         "Generated question violated exclude_topics, retrying attempt %d",
                #         attempt,
                #     )
                #     continue

                return question_text

            except (APIConnectionError, RateLimitError, APITimeoutError, InternalServerError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "Transient error during question generation attempt %d: %s",
                    attempt,
                    str(exc),
                )
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
            except Exception as exc:
                last_error = exc
                logger.error("Non-retryable error during question generation: %s", str(exc))
                break

        # If retries exhausted and in development, fallback gracefully with log
        # if settings.ENVIRONMENT == "development":
        #     logger.warning(
        #         "Exhausted Azure OpenAI attempts in development. Falling back to simulated question. Error: %s",
        #         str(last_error),
        #     )
        #     return self._generate_fallback_question(difficulty, include_topics, question_index)

        raise AppException(
            code="QUESTION_GENERATION_FAILED",
            message=f"Failed to generate interview question: {str(last_error)}",
            status_code=502,
        )

    async def generate_next_question_for_session(
        self,
        db: Any,
        session_id: Any,
    ) -> Optional[Any]:
        """Orchestrates generation and persistence of subsequent questions for an active session."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.session import Session
        from app.models.question import Question

        stmt = (
            select(Session)
            .options(selectinload(Session.questions).selectinload(Question.answer))
            .where(Session.id == session_id)
        )
        res = await db.execute(stmt)
        session_obj = res.scalar_one_or_none()

        if not session_obj or session_obj.ended_at is not None:
            return None

        questions_sorted = sorted(session_obj.questions, key=lambda q: q.idx)
        next_idx = len(questions_sorted) + 1
        if next_idx > session_obj.max_questions:
            return None

        prior_interactions = [
            {
                "index": q.idx,
                "question": q.text,
                "answer_summary": (q.answer.transcript if q.answer else "Not answered yet")[:300],
            }
            for q in questions_sorted
        ]

        question_text = await self.generate_question(
            difficulty=session_obj.difficulty,
            resume_text=session_obj.resume_text,
            jd_text=session_obj.jd_text,
            include_topics=session_obj.include_topics,
            exclude_topics=session_obj.exclude_topics,
            question_index=next_idx,
            max_questions=session_obj.max_questions,
            prior_interactions=prior_interactions,
        )

        next_question = Question(
            session_id=session_obj.id,
            idx=next_idx,
            text=question_text,
        )
        db.add(next_question)
        await db.commit()
        await db.refresh(next_question)
        return next_question


question_generator = QuestionGenerator()

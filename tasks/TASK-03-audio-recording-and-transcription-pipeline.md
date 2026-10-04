# TASK-03: Audio Ingestion & Transcription Pipeline

## 1. Metadata
- **Task ID:** TASK-03
- **Title:** Audio Ingestion, Jargon-Seeded Transcription & Answer Processing
- **Milestone:** M2 (Voice Pipeline & Audio Processing)
- **Component:** Backend API & Speech-to-Text (`faster-whisper`)
- **Dependencies:** [TASK-01](./TASK-01-database-and-backend-foundation.md), [TASK-02](./TASK-02-session-management-and-question-generation.md)

---

## 2. Objective & Scope
Implement the voice ingestion pipeline, in-process speech-to-text transcription using `faster-whisper` (`base.en`, `int8` CPU), jargon prompt seeding from the session's JD and resume, empty/silent audio rejection, answer record persistence, queue event dispatch, and simultaneous generation of the next question.

---

## 3. Technical Requirements

### 3.1 In-Process Speech-to-Text Service
Create `app/services/transcription_service.py`:
- Use `faster-whisper`:
  ```python
  from faster_whisper import WhisperModel

  # Model loaded once at application lifespan startup
  model = WhisperModel("base.en", device="cpu", compute_type="int8")
  ```
- **Domain Jargon Prompt Seeding:**
  - Whisper models support `initial_prompt` to bias spelling towards uncommon vocabulary.
  - Extract top technical keywords from the session's Resume and JD (e.g., "Kubernetes, Istio, Kafka, PostgreSQL, idempotency, Prometheus, CI/CD, CQRS").
  - Pass this comma-separated keyword string into `model.transcribe(..., initial_prompt=seeded_jargon)`.
- **Transcription Execution:**
  - Execute CPU-bound transcription in `asyncio.to_thread` or thread pool to avoid blocking the FastAPI async event loop.
  - Transcribe audio buffer/temporary file.
  - Extract text and calculate duration `audio_seconds`.

### 3.2 Audio File & Privacy Handling
- Audio is read directly into memory or written to an ephemeral `tempfile.NamedTemporaryFile`.
- **Strict Privacy Rule:** Audio is strictly ephemeral. Immediately delete temporary files in a `finally` block post-transcription. Never upload or store audio blobs in Supabase or object storage.
- **Audio Validation:**
  - Supported MIME types: `audio/webm`, `audio/ogg`, `audio/wav`, `audio/mp4`, `audio/x-m4a`.
  - Max upload size: 10 MB (enforce in middleware or endpoint streaming check). Return `413 PAYLOAD_TOO_LARGE` if exceeded.
  - Return `415 UNSUPPORTED_MEDIA_TYPE` if MIME type is invalid.
- **Silence / Empty Audio Detection:**
  - If transcribed text is empty, whitespace-only, or contains solely silence tokens (e.g. `[BLANK_AUDIO]`, `Thank you.`, `You`), return `400 BAD_INPUT` with `{ "error": { "code": "EMPTY_AUDIO", "message": "No speech detected in audio. Please check your microphone and try again." } }`.
  - In this scenario, do **not** create an answer row or advance question index.

### 3.3 Answer Submission Endpoint

#### `POST /api/v1/sessions/{id}/answers`
- **Content-Type:** `multipart/form-data`
- **Form Fields:**
  - `question_id`: UUID
  - `audio`: File upload (binary)
  - `text_fallback`: Optional string (for users opting out of microphone or submitting text fallback)
- **Response (200 OK):**
  ```json
  {
    "answer_id": "97e68cf3-1577-4b72-a0f5-4f36c53e028b",
    "transcript": "In our payment gateway, we ensured idempotency by storing transaction idempotency keys in Redis with a 24-hour TTL...",
    "next_question": {
      "id": "c869e54d-7bc4-411a-8bb7-d8d4791a8ea9",
      "index": 2,
      "text": "What strategies did you use to handle Redis failover or network partitioning during peak transactions?"
    },
    "done": false
  }
  ```
  *(When the session reaches `max_questions`, `next_question` is `null` and `done` is `true`)*.

- **Execution Flow & Sequence:**
  1. Validate session exists and `ended_at IS NULL`. (If ended, return `409 CONFLICT`).
  2. Validate `question_id` belongs to `session_id` and has no existing answer. (If answered, return `409 CONFLICT`).
  3. If `audio` is provided: validate size/type, transcribe with `faster-whisper` and jargon prompt, calculate `audio_seconds`, sanitize and clean temp file.
  4. If `text_fallback` is provided: use provided text directly, `audio_seconds = 0`.
  5. Check for empty transcription.
  6. DB Transaction:
     - Insert answer row into `answers` table (`question_id`, `session_id`, `transcript`, `audio_seconds`, `status = 'pending'`, `attempts = 0`).
  7. Check question limit:
     - Count total answered questions for session.
     - If `count >= session.max_questions`: mark session `ended_at = NOW()`, set `next_question = None`, `done = True`.
     - Else: invoke `QuestionGenerator` passing prior Q&As, insert new question into `questions` table (`idx = current + 1`), set `next_question = { id, index, text }`, `done = False`.
  8. Enqueue evaluation message to Azure Storage Queue:
     ```json
     {
       "answer_id": "97e68cf3-1577-4b72-a0f5-4f36c53e028b",
       "session_id": "a3bb101a-8269-4a4c-9f8b-201efb5e5a2b",
       "attempt": 1
     }
     ```
  9. Commit DB and return response.

---

## 4. Performance & Latency Budgets
- Fast transcription on CPU: `base.en` with int8 quantization transcribes ~60 seconds of speech in approximately 1.5–2.5 seconds on modern x86/ARM vCPU.
- LLM next-question generation: ~1.5–2.5 seconds on `gpt-4o-mini`.
- Total submit-to-next-question response time target: **< 5s average, < 8s p95**.
- Background evaluation occurs entirely decoupled from this request.

---

## 5. Implementation Steps
1. Add `faster-whisper` to backend dependencies. Ensure necessary native dependencies (`ffmpeg`, `libgomp`) are documented in `Dockerfile`.
2. Implement model lifecycle loader in `app/main.py` using FastAPI lifespan context.
3. Build keyword extractor utility to parse technical terms from JD/resume.
4. Implement `app/services/transcription_service.py` with thread offloading.
5. Implement `app/services/queue_service.py` to send messages to Azure Storage Queue `evaluation-jobs`.
6. Implement `POST /api/v1/sessions/{id}/answers` endpoint in `app/api/v1/endpoints/answers.py`.
7. Write unit tests for silence detection and jargon prompting.

---

## 6. Acceptance Criteria
- [ ] `faster-whisper` loads once at server startup; subsequent requests reuse the in-memory model.
- [ ] Submitting a 30-second technical audio clip transcribes specialized keywords accurately (e.g., "Kubernetes", "gRPC").
- [ ] Audio files are removed from the filesystem after transcription completes, even on error.
- [ ] An answer row with `status = 'pending'` is created in Supabase.
- [ ] An evaluation message is pushed to the Azure Storage Queue.
- [ ] The next question is returned immediately without waiting for evaluation.
- [ ] Reaching `max_questions` returns `done = true` and `next_question = null`.

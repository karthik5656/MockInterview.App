# Mock Interview Application: Technical Specification

**Status:** Draft v1 | **Cost target:** \~$0/month (free tiers only, LLM pay-per-use in pennies)

---

## 1. Overview

An AI-driven interview preparation tool. A candidate supplies a Resume and Job Description (JD), answers questions by voice, and receives a per-question and overall evaluation (STAR adherence, technical depth, missing JD keywords, suggested rewrite).

### 1.1 Goals

- Voice-first answers with accurate transcription of technical jargon
- Non-blocking UX: evaluation runs in the background while the next question is shown
- Final dashboard with scores and critiques
- Operating cost at or near $0/month

### 1.2 Non-Goals (v1)

- Live/streaming transcription, barge-in, voice-to-voice conversation
- Multi-user accounts, billing, team features
- Video capture or proctoring

---

## 2. Architecture

| Component | Technology | Hosting |
| --- | --- | --- |
| Frontend | React (Vite or Next.js) | Azure Static Web Apps (Free) |
| Backend API | Python + FastAPI | Azure Container Apps (Free grant) |
| Speech-to-Text | `faster-whisper` (`base.en`, int8) | In-process on backend CPU |
| Database | PostgreSQL | Supabase Free |
| Event broker | Azure Storage Queues | Azure Storage |
| Background worker | Azure Functions (Python, queue trigger) | Consumption plan |
| LLM | Azure OpenAI `gpt-4o-mini` | Serverless, pay-as-you-go |

### 2.1 Communication Style

**REST over HTTPS** for all client-server interaction. The flow is turn-based request/response, which suits stateless, scale-to-zero hosting. No WebSocket server in v1.

### 2.2 Request Flow

1. UI records audio with `MediaRecorder` and `POST`s the blob to the API.
2. API transcribes with `faster-whisper`, stores the answer in Supabase (`status = pending`), and enqueues an evaluation message.
3. API generates the next question via `gpt-4o-mini` and returns it in the same response.
4. Azure Function dequeues the message, loads context from Supabase, calls the evaluator LLM, and writes the JSON critique back (`status = evaluated`).
5. Dashboard reads results via `GET`, polling until all answers are evaluated.

---

## 3. Functional Requirements

| ID | Requirement |
| --- | --- |
| FR-1 | User can paste or upload Resume and JD (text, PDF, DOCX; extracted to plain text server-side) |
| FR-2 | User selects difficulty (Junior, Mid, Senior, Staff) and include/exclude topics |
| FR-3 | System generates question 1 from resume, JD, difficulty, and topics |
| FR-4 | User records and stops; audio is transcribed and saved |
| FR-5 | Next question is returned immediately after submission, without waiting for evaluation |
| FR-6 | Questions avoid repeating earlier ones and may follow up on prior answers |
| FR-7 | Interview ends on user action or at a max question limit (default 10) |
| FR-8 | Dashboard shows overall score /10, and per question: transcript, STAR critique, technical depth, missing points, suggested answer |
| FR-9 | Dashboard shows evaluation progress ("4 of 6 evaluated") and handles failed evaluations with a retry |
| FR-10 | User can review the transcript and re-record before submitting (v1.1 stretch) |

---

## 4. Non-Functional Requirements

- **Latency:** Submit-to-next-question under 8s p95 (transcription of a \~60s clip on CPU plus one LLM call)
- **Cost:** Stay within free tiers; LLM spend under \~$1/month at personal-use volume
- **Reliability:** Evaluation is at-least-once and idempotent; failures never lose a transcript
- **Privacy:** Resume/JD and audio treated as sensitive; audio discarded after transcription; row-level isolation per session
- **Accessibility:** Keyboard-operable recording controls; visible recording state; text fallback input

---

## 5. API Specification

Base path: `/api/v1`. JSON unless noted.

### `POST /sessions`

Create a session and return the first question.

```json
// Request
{
  "resume_text": "string",
  "jd_text": "string",
  "difficulty": "senior",
  "include_topics": ["system design", "microservices"],
  "exclude_topics": ["frontend"],
  "max_questions": 10
}
// Response 201
{
  "session_id": "uuid",
  "question": { "id": "uuid", "index": 1, "text": "string" }
}
```

### `POST /sessions/{id}/answers`

`multipart/form-data`: `audio` (webm/ogg/wav), `question_id`.

```json
// Response 200
{
  "answer_id": "uuid",
  "transcript": "string",
  "next_question": { "id": "uuid", "index": 2, "text": "string" },
  "done": false
}
```

`next_question` is `null` and `done` is `true` when the limit is reached.

### `POST /sessions/{id}/end`

Marks the session ended. Returns `{ "status": "ended", "pending_evaluations": 2 }`.

### `GET /sessions/{id}/results`

```json
{
  "status": "ended",
  "progress": { "total": 6, "evaluated": 4, "failed": 0 },
  "overall_score": 7.2,
  "items": [
    {
      "question": "string",
      "transcript": "string",
      "status": "evaluated",
      "evaluation": {
        "score": 7,
        "star": { "situation": 2, "task": 1, "action": 2, "result": 1, "notes": "string" },
        "technical_depth": { "score": 7, "notes": "string" },
        "missing_points": ["idempotency", "dead-letter queue"],
        "suggested_answer": "string"
      }
    }
  ]
}
```

`overall_score` is `null` until all items are evaluated or failed.

### `POST /answers/{id}/retry`

Re-enqueues a failed evaluation.

### Errors

Standard shape: `{ "error": { "code": "string", "message": "string" } }`. Codes: `400` bad input, `404` unknown session, `409` session already ended, `413` audio too large, `415` unsupported audio type, `429` rate limited.

---

## 6. Data Model (Supabase / PostgreSQL)

```sql
sessions (
  id uuid pk, created_at timestamptz, ended_at timestamptz,
  resume_text text, jd_text text, difficulty text,
  include_topics text[], exclude_topics text[],
  max_questions int, overall_score numeric(3,1)
)

questions (
  id uuid pk, session_id uuid fk, idx int,
  text text, created_at timestamptz,
  unique (session_id, idx)
)

answers (
  id uuid pk, question_id uuid fk unique, session_id uuid fk,
  transcript text, audio_seconds numeric,
  status text check (status in ('pending','evaluated','failed')),
  attempts int default 0, created_at timestamptz
)

evaluations (
  answer_id uuid pk fk, score int, star jsonb,
  technical_depth jsonb, missing_points text[],
  suggested_answer text, model text, evaluated_at timestamptz
)
```

Access: backend and worker use the service-role key. If the frontend subscribes via Supabase Realtime, add RLS scoped to a per-session token.

---

## 7. Component Design

### 7.1 Frontend

- **Screens:** Configure, Interview, Results
- **Recording:** `MediaRecorder` with `audio/webm;codecs=opus`; hard cap of 3 minutes per answer; show timer and level meter
- **State:** session id in memory plus `sessionStorage` to survive refresh
- **Results:** poll `GET /results` every 2-3s with backoff while `evaluated + failed < total`; stop on completion

### 7.2 Backend (FastAPI)

- **Transcription:** load `faster-whisper` `base.en` once at startup (`compute_type="int8"`, CPU); pass an `initial_prompt` seeded with domain terms from the JD and resume (e.g. "Kubernetes, SNS, SQS, idempotency") to improve jargon accuracy
- **Question generation:** prompt includes resume, JD, difficulty, topic filters, and prior Q&A summaries; request structured JSON output
- **Queueing:** enqueue `{ answer_id, session_id }` after the DB write commits
- **Audio handling:** read into memory or a temp file, delete after transcription; never persist audio

### 7.3 Evaluation Worker (Azure Function)

- Queue trigger on `evaluation-jobs`
- Loads question, transcript, JD, resume, difficulty
- Calls `gpt-4o-mini` with a rubric prompt, JSON mode, temperature around 0.2
- Validates output against a schema; upserts `evaluations` and sets `answers.status = evaluated`
- On failure, throw so the queue retries; after max dequeue count the message moves to `evaluation-jobs-poison` and a handler sets `status = failed`

### 7.4 Evaluation Rubric

Each answer is scored 0-10 on: STAR structure, technical correctness and depth, relevance to the JD, and communication clarity. Output includes missing JD keywords and a rewritten answer. Overall session score is the mean of evaluated item scores.

---

## 8. Reliability and Edge Cases

| Case | Handling |
| --- | --- |
| Duplicate queue delivery | Upsert on `answer_id`; skip if already `evaluated` |
| LLM returns invalid JSON | Schema validation, retry once with a repair prompt, then fail to retry path |
| Empty or silent audio | Return `400` with a prompt to re-record; no answer row created |
| Container cold start | Preload the model at startup; show "Warming up" state on first request |
| User ends with pending evaluations | Dashboard shows partial results with progress and fills in as they finish |
| Browser denies mic permission | Show instructions and offer text input fallback |
| Session reuse after end | `409` on further answers |

---

## 9. Security and Privacy

- Validate content type and enforce size limits (e.g. 10 MB audio) on upload
- Rate limit per IP on session creation and answer submission to protect free-tier quotas and LLM spend
- CORS restricted to the Static Web App origin
- Secrets (Supabase key, Azure OpenAI key, storage connection string) in Container Apps secrets and Function app settings, never in the frontend
- Session IDs are unguessable UUIDs; consider a signed session token for v1.1
- Provide a "delete my session" endpoint that removes all rows for a session

---

## 10. Cost Controls

- Azure Container Apps: scale to zero, 1 replica max, 1 vCPU / 2 GiB
- Cap `max_questions`, answer length, and prompt size (truncate resume/JD to a token budget)
- Use `gpt-4o-mini` only; set a monthly budget alert on the Azure subscription
- Supabase Free pauses inactive projects, so add a lightweight keep-alive or accept a cold resume
- Monitor Container Apps free vCPU-seconds and GiB-seconds in the Azure portal

---

## 11. Observability

- Structured JSON logs with `session_id` and `answer_id` correlation
- Application Insights (free allowance) for API and Function traces
- Track: transcription time, LLM latency and token counts, queue age, evaluation failure rate

---

## 12. Testing Strategy

- **Unit:** prompt builders, schema validation, score aggregation
- **Integration:** API with a stub LLM and local Postgres; worker against Azurite (Storage emulator)
- **Transcription quality:** a small fixed set of recorded technical answers with expected keywords; track word error rate on jargon
- **E2E:** Playwright with a fake media stream for the record, submit, results path

---

## 13. Milestones

| Phase | Scope |
| --- | --- |
| M1 | Config screen, `POST /sessions`, question generation, text-only answers |
| M2 | Audio capture, `faster-whisper` transcription, answer persistence |
| M3 | Queue plus Azure Function evaluator, `GET /results` with polling |
| M4 | Dashboard UI, retry/failure handling, rate limits, budget alerts |
| M5 | Polish: re-record, Supabase Realtime upgrade, delete-session, accessibility pass |

---

## 14. Open Questions

1. Is the app single-user (personal) or will it be shared? This decides whether auth is needed in v1.
2. Should the interviewer read questions aloud (browser `speechSynthesis`, free) or display text only?
3. Is `base.en` accurate enough on your jargon, or should `small.en` be benchmarked against the free-tier CPU limit?
4. Retention: how long should transcripts and evaluations be kept?

---

## 15. Future Considerations

- WebSocket or WebRTC streaming with a hosted STT service for live, conversational interviews
- Adaptive difficulty based on running scores
- Progress tracking across multiple sessions
- Exportable PDF report of results
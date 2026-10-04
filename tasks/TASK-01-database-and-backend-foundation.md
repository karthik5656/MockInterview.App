# TASK-01: Database Schema & Backend Foundation

## 1. Metadata
- **Task ID:** TASK-01
- **Title:** Database Schema & Backend Foundation
- **Milestone:** M1 (Foundation & Core Setup)
- **Component:** Backend API (FastAPI) & Database (PostgreSQL / Supabase)
- **Dependencies:** None

---

## 2. Objective & Scope
Establish the backend application architecture with FastAPI, implement the PostgreSQL database schema on Supabase, configure database migrations, define standardized API request/response models, and setup environment configuration for local and cloud deployment.

---

## 3. Technical Requirements

### 3.1 Project Structure
Organize the backend under `src/backend` with a clean modular structure:
```text
src/backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── sessions.py
│   │   │   │   ├── answers.py
│   │   │   │   └── results.py
│   │   │   └── api.py
│   │   └── errors.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   ├── models/
│   │   ├── session.py
│   │   ├── question.py
│   │   ├── answer.py
│   │   └── evaluation.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── session.py
│   │   ├── question.py
│   │   ├── answer.py
│   │   └── evaluation.py
│   ├── services/
│   └── main.py
├── migrations/
│   └── 001_initial_schema.sql
├── tests/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

### 3.2 Database Schema (Supabase / PostgreSQL)
Create `migrations/001_initial_schema.sql` implementing the specification tables, constraints, foreign keys, and indexes:

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ NULL,
    resume_text TEXT NOT NULL,
    jd_text TEXT NOT NULL,
    difficulty VARCHAR(20) NOT NULL CHECK (difficulty IN ('junior', 'mid', 'senior', 'staff')),
    include_topics TEXT[] NOT NULL DEFAULT '{}',
    exclude_topics TEXT[] NOT NULL DEFAULT '{}',
    max_questions INT NOT NULL DEFAULT 10 CHECK (max_questions > 0 AND max_questions <= 20),
    overall_score NUMERIC(3, 1) NULL CHECK (overall_score >= 0.0 AND overall_score <= 10.0)
);

CREATE INDEX idx_sessions_created_at ON sessions(created_at DESC);

-- 2. questions table
CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    idx INT NOT NULL CHECK (idx >= 1),
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_session_question_index UNIQUE (session_id, idx)
);

CREATE INDEX idx_questions_session_id ON questions(session_id);

-- 3. answers table
CREATE TABLE IF NOT EXISTS answers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question_id UUID NOT NULL UNIQUE REFERENCES questions(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    transcript TEXT NOT NULL,
    audio_seconds NUMERIC(6, 2) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'evaluated', 'failed')),
    attempts INT NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_answers_session_id ON answers(session_id);
CREATE INDEX idx_answers_status ON answers(status);

-- 4. evaluations table
CREATE TABLE IF NOT EXISTS evaluations (
    answer_id UUID PRIMARY KEY REFERENCES answers(id) ON DELETE CASCADE,
    score INT NOT NULL CHECK (score >= 0 AND score <= 10),
    star JSONB NOT NULL,
    technical_depth JSONB NOT NULL,
    missing_points TEXT[] NOT NULL DEFAULT '{}',
    suggested_answer TEXT NOT NULL,
    model VARCHAR(100) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Row-Level Security (RLS) policies
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY;

-- Backend Service Role Bypass (or permissive policy for direct connection strings)
CREATE POLICY "Service role full access on sessions" ON sessions FOR ALL USING (true);
CREATE POLICY "Service role full access on questions" ON questions FOR ALL USING (true);
CREATE POLICY "Service role full access on answers" ON answers FOR ALL USING (true);
CREATE POLICY "Service role full access on evaluations" ON evaluations FOR ALL USING (true);
```

### 3.3 Core Configuration & Database Connection
- Use `pydantic-settings` to load settings from `.env` or system environment variables:
  - `DATABASE_URL`: PostgreSQL connection string (asyncpg / psycopg).
  - `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME` (default: `gpt-4o-mini`).
  - `AZURE_STORAGE_CONNECTION_STRING`, `EVALUATION_QUEUE_NAME` (`evaluation-jobs`).
  - `CORS_ORIGINS`: Allowed origins (e.g. `http://localhost:5173`, Azure Static Web Apps URL).
  - `ENVIRONMENT`: `development` | `production`.
  - `LOG_LEVEL`: `INFO` | `DEBUG`.
- Connection pooling: Configure async SQLAlchemy (`create_async_engine`) or `asyncpg` pool with low connection count (`pool_size=5`, `max_overflow=5`) to fit Supabase free tier connection boundaries.

### 3.4 Error Handling & Standard Error Response Schema
Implement standard error formatting middleware and exception handlers in FastAPI matching spec Section 5:
```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Detailed error message"
  }
}
```
HTTP status code mappings:
- `400`: `BAD_INPUT` (missing fields, invalid audio, validation failures)
- `404`: `NOT_FOUND` (session or answer not found)
- `409`: `CONFLICT` (session already ended, answer already submitted for question)
- `413`: `PAYLOAD_TOO_LARGE` (audio exceeds size cap, e.g. 10MB)
- `415`: `UNSUPPORTED_MEDIA_TYPE` (non-audio MIME types)
- `429`: `RATE_LIMITED` (exceeded requests quota)
- `500`: `INTERNAL_SERVER_ERROR` (unexpected exceptions)

---

## 4. Implementation Steps
1. Initialize `src/backend` with `pyproject.toml` and `requirements.txt` containing dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `azure-storage-queue`, `openai`, `faster-whisper`, `python-multipart`.
2. Write `app/core/config.py` using `BaseSettings` with strict validation.
3. Write `app/core/database.py` with async database session lifecycle (`async_sessionmaker`, dependency injection `get_db`).
4. Write SQL migration script `migrations/001_initial_schema.sql` and verify execution against Supabase.
5. Create Pydantic v2 schemas for all domain entities in `app/schemas/`.
6. Write centralized exception handlers in `app/api/errors.py`.
7. Configure FastAPI application entrypoint in `app/main.py` with CORS middleware, lifespan events, and health check route `GET /health`.

---

## 5. Acceptance Criteria
- [ ] Backend starts cleanly with `uvicorn app.main:app --reload` on port 8000.
- [ ] Database schema is applied on PostgreSQL; all 4 tables with foreign keys and check constraints exist.
- [ ] Health check endpoint `GET /health` returns `{ "status": "healthy", "database": "connected" }`.
- [ ] Unhandled exceptions or standard errors return the exact `{ "error": { "code": "...", "message": "..." } }` contract with matching HTTP status codes.
- [ ] CORS allows development localhost and configured frontend origin.

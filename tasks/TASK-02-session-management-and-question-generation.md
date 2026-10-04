# TASK-02: Session Management & Question Generation

## 1. Metadata
- **Task ID:** TASK-02
- **Title:** Session Management & Question Generation Engine
- **Milestone:** M1 (Foundation & Core Setup)
- **Component:** Backend API & LLM Service
- **Dependencies:** [TASK-01](./TASK-01-database-and-backend-foundation.md)

---

## 2. Objective & Scope
Implement interview session initialization, document parsing (plain text, PDF, DOCX), topic/difficulty parameter validation, dynamic first question generation using Azure OpenAI `gpt-4o-mini`, session termination, and subsequent question generation context orchestration.

---

## 3. Technical Requirements

### 3.1 Document Text Extraction Service
Create `app/services/document_parser.py`:
- Support parsing uploaded files or raw strings:
  - **PDF:** Extract using `pypdf` or `pymupdf`. Sanitize whitespace and strip headers/footers.
  - **DOCX:** Extract using `python-docx`. Concatenate paragraph text.
  - **Plain Text / UTF-8:** Direct string decoding.
- **Token Budget Guard:** Truncate resume text to max 2,500 words and JD text to max 2,000 words if they exceed typical limits to prevent context overflow and protect cost quotas.

### 3.2 Question Generation Service
Create `app/services/question_generator.py`:
- Use Azure OpenAI client targeting deployment model `gpt-4o-mini`.
- Parameters: `temperature=0.7`, `response_format={"type": "json_object"}`.
- System prompt instructions:
  - Role: Senior Technical Interviewer calibrated to the specified difficulty (`junior`, `mid`, `senior`, `staff`).
  - Anchor questions in the intersection of the candidate's Resume and the Job Description.
  - Adhere to `include_topics` (mandatory coverage) and strictly avoid `exclude_topics`.
  - Question 1 must start with an introductory or foundational role-relevant challenge tailored to the resume background.
  - Subsequent questions must branch dynamically: either follow up on candidate's prior answer depth, or pivot to an uncovered JD requirement.
  - Never repeat a previously asked question.
- Prompt Context Schema:
  ```json
  {
    "difficulty": "senior",
    "resume": "<truncated_resume_text>",
    "job_description": "<truncated_jd_text>",
    "include_topics": ["system design", "microservices"],
    "exclude_topics": ["frontend"],
    "question_index": 1,
    "max_questions": 10,
    "prior_interactions": [
      {
        "index": 1,
        "question": "...",
        "answer_summary": "..."
      }
    ]
  }
  ```
- LLM Output Schema:
  ```json
  {
    "question_text": "In your previous role at Company X, how did you handle data consistency across microservices during network partitions?"
  }
  ```

### 3.3 API Endpoints Specification

#### 1. `POST /api/v1/sessions`
- **Request Body (JSON):**
  ```json
  {
    "resume_text": "string (min 50 chars)",
    "jd_text": "string (min 50 chars)",
    "difficulty": "junior | mid | senior | staff",
    "include_topics": ["string"],
    "exclude_topics": ["string"],
    "max_questions": 10
  }
  ```
- **Optional File Upload Variant:** `POST /api/v1/sessions/upload` accepting `multipart/form-data` with `resume_file` and `jd_file`.
- **Response (201 Created):**
  ```json
  {
    "session_id": "a3bb101a-8269-4a4c-9f8b-201efb5e5a2b",
    "question": {
      "id": "e4028b08-b39b-4682-8bc9-9372ef35b2e3",
      "index": 1,
      "text": "Can you walk me through your experience designing high-throughput message pipelines using Kafka?"
    }
  }
  ```
- **Logic:**
  1. Validate difficulty is one of `['junior', 'mid', 'senior', 'staff']`.
  2. Validate `max_questions` between 1 and 20 (default 10).
  3. Insert row into `sessions` table.
  4. Invoke `QuestionGenerator` to generate question 1.
  5. Insert row into `questions` table (`idx=1`, `session_id`, `text`).
  6. Return `session_id` and first question payload.

#### 2. `POST /api/v1/sessions/{id}/end`
- **Response (200 OK):**
  ```json
  {
    "status": "ended",
    "pending_evaluations": 2
  }
  ```
- **Logic:**
  1. Fetch session by ID. If not found, return `404 NOT_FOUND`.
  2. If `ended_at` is already populated, return `409 CONFLICT` ("Session already ended").
  3. Set `ended_at = NOW()`.
  4. Query count of answers where `session_id = id` and `status = 'pending'`.
  5. Return updated status and pending count.

---

## 4. Implementation Steps
1. Install `pypdf`, `python-docx`, `tiktoken`, and `openai` in backend environment.
2. Implement `app/services/document_parser.py` with unit tests for plain text, PDF, and DOCX files.
3. Implement `app/services/question_generator.py` with retry logic for Azure OpenAI transient errors and JSON validation.
4. Create route handlers in `app/api/v1/endpoints/sessions.py`.
5. Connect database operations using async SQLAlchemy sessions.
6. Write integration tests simulating session creation, question 1 generation, and early session termination.

---

## 5. Acceptance Criteria
- [ ] Submitting valid resume and JD via `POST /api/v1/sessions` generates a contextually tailored first question in under 3.5 seconds.
- [ ] Topics in `exclude_topics` are never present in the generated question text.
- [ ] Topics in `include_topics` are prioritized.
- [ ] Sessions and questions are committed correctly to Supabase PostgreSQL.
- [ ] `POST /api/v1/sessions/{id}/end` sets `ended_at` timestamp and returns accurate count of pending evaluations.
- [ ] Subsequent calls to end an already ended session return `409 CONFLICT`.

# TASK-04: Asynchronous Evaluation Worker & Queue System

## 1. Metadata
- **Task ID:** TASK-04
- **Title:** Asynchronous Evaluation Worker & Queue Processing System
- **Milestone:** M3 (Asynchronous Evaluation Engine)
- **Component:** Background Worker (Azure Functions / Python) & Azure Storage Queue
- **Dependencies:** [TASK-01](./TASK-01-database-and-backend-foundation.md), [TASK-03](./TASK-03-audio-recording-and-transcription-pipeline.md)

---

## 2. Objective & Scope
Implement the asynchronous background worker using Azure Functions (Python v2 programming model) triggered by the `evaluation-jobs` Azure Storage Queue. The worker loads interview context from Supabase, performs structured LLM evaluation with Azure OpenAI `gpt-4o-mini` based on a standardized rubric, validates the JSON schema, updates database state idempotently, and routes failed jobs through poison queue handling.

---

## 3. Technical Requirements

### 3.1 Worker Project Structure
Create the worker under `src/worker/`:
```text
src/worker/
├── function_app.py
├── host.json
├── local.settings.json
├── requirements.txt
├── services/
│   ├── database.py
│   ├── evaluator.py
│   └── prompts.py
└── schemas/
    └── evaluation_schema.py
```

### 3.2 Evaluation Rubric & Prompt Engineering
Create `src/worker/services/prompts.py`:
- Use `gpt-4o-mini` with `temperature=0.2` and `response_format={"type": "json_object"}`.
- System prompt instructions:
  - Act as an elite Principal Bar-Raiser and Technical Evaluator.
  - Assess candidate response according to:
    1. **STAR Adherence:**
       - Situation: Clear context and business/technical setting (0-2)
       - Task: Clear problem statement and objective (0-2)
       - Action: Detailed specific technical actions taken by the candidate (0-3)
       - Result: Quantifiable business or technical outcome/impact (0-3)
       - STAR Notes: Constructive commentary on structural delivery.
    2. **Technical Depth:**
       - Score: 0 to 10 based on architecture decisions, trade-offs, algorithms, failure handling, and seniority level expectation.
       - Notes: Specific praise and critique of technical accuracy and complexity.
    3. **Missing Points / JD Keywords:**
       - Extract 2-5 crucial technical keywords or architectural patterns directly relevant to the JD that the candidate failed to mention.
    4. **Suggested Answer:**
       - Provide a concrete, exemplary rewrite of the answer adhering to STAR format with high technical rigor.
    5. **Overall Item Score:**
       - A balanced integer score between 0 and 10 representing overall interview readiness for this question.

### 3.3 Output Schema & Validation
Create Pydantic model in `src/worker/schemas/evaluation_schema.py`:
```python
from pydantic import BaseModel, Field
from typing import List

class StarCritique(BaseModel):
    situation: int = Field(ge=0, le=2)
    task: int = Field(ge=0, le=2)
    action: int = Field(ge=0, le=3)
    result: int = Field(ge=0, le=3)
    notes: str

class TechnicalDepthCritique(BaseModel):
    score: int = Field(ge=0, le=10)
    notes: str

class EvaluationPayload(BaseModel):
    score: int = Field(ge=0, le=10)
    star: StarCritique
    technical_depth: TechnicalDepthCritique
    missing_points: List[str]
    suggested_answer: str
```

### 3.4 Queue Trigger & Idempotent Processing Flow
Create Azure Function trigger in `function_app.py`:
```python
import azure.functions as func

app = func.FunctionApp()

@app.queue_trigger(
    arg_name="msg",
    queue_name="evaluation-jobs",
    connection="AzureWebJobsStorage"
)
async def process_evaluation_job(msg: func.QueueMessage) -> None:
    ...
```

**Worker Lifecycle Steps:**
1. **Decode Message:** Parse `{ "answer_id": "...", "session_id": "...", "attempt": 1 }`.
2. **Idempotency Check:**
   - Query DB for answer where `id = answer_id`.
   - If `status == 'evaluated'`, log info and return immediately without re-evaluating.
3. **Fetch Context:**
   - Query answer transcript.
   - Query question text.
   - Query session resume, JD, and difficulty.
4. **Invoke LLM:**
   - Call Azure OpenAI `gpt-4o-mini`.
   - Parse JSON and validate against `EvaluationPayload`.
   - **Schema Recovery:** If JSON parsing fails, retry once with a corrective repair prompt (`"The previous output had schema errors: {errors}. Fix the JSON to strictly conform to schema."`).
5. **Database Persistence:**
   - In a transaction:
     - Insert or update `evaluations` record:
       ```sql
       INSERT INTO evaluations (answer_id, score, star, technical_depth, missing_points, suggested_answer, model, evaluated_at)
       VALUES (:answer_id, :score, :star, :technical_depth, :missing_points, :suggested_answer, 'gpt-4o-mini', NOW())
       ON CONFLICT (answer_id) DO UPDATE SET
         score = EXCLUDED.score,
         star = EXCLUDED.star,
         technical_depth = EXCLUDED.technical_depth,
         missing_points = EXCLUDED.missing_points,
         suggested_answer = EXCLUDED.suggested_answer,
         evaluated_at = NOW();
       ```
     - Update `answers` table: `status = 'evaluated'`, `attempts = attempts + 1`.
6. **Error & Poison Queue Handling:**
   - If an unhandled exception or LLM failure occurs, raise exception so Azure Storage Queue retries with exponential backoff up to 5 attempts (configured in `host.json`).
   - Create poison queue trigger `@app.queue_trigger(arg_name="msg", queue_name="evaluation-jobs-poison", connection="AzureWebJobsStorage")`:
     - When a message reaches the poison queue, update `answers` table: `status = 'failed'`, `attempts = 5`.
     - Log alert to Application Insights.

### 3.5 Host Configuration (`host.json`)
```json
{
  "version": "2.0",
  "extensions": {
    "queues": {
      "maxPollingInterval": "00:00:02",
      "visibilityTimeout": "00:00:30",
      "batchSize": 4,
      "maxDequeueCount": 5
    }
  }
}
```

---

## 4. Implementation Steps
1. Create `src/worker` project with Python Functions v2 runtime (`azure-functions`, `openai`, `pydantic`, `asyncpg`, `sqlalchemy`).
2. Implement evaluation prompt builder and Pydantic validator.
3. Implement `process_evaluation_job` and poison queue handler `process_poison_job`.
4. Configure local emulation using Azurite for queue storage and Supabase PostgreSQL.
5. Create test scripts to enqueue test messages and assert database output.

---

## 5. Acceptance Criteria
- [ ] Worker dequeues message, parses payload, and fetches session context from Supabase.
- [ ] Evaluation output conforms strictly to `EvaluationPayload` schema.
- [ ] Evaluations table is populated with score, STAR breakdown, technical depth, missing points, and suggested answer.
- [ ] `answers.status` updates from `pending` to `evaluated`.
- [ ] Duplicate deliveries on the same `answer_id` do not cause duplicate LLM charges or database errors.
- [ ] Poison queue handler reliably marks persistently failing answers as `failed` in the database.

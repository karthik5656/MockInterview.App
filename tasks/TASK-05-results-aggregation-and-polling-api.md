# TASK-05: Results Aggregation, Polling API & Session Deletion

## 1. Metadata
- **Task ID:** TASK-05
- **Title:** Results Aggregation, Polling Endpoints & Session Lifecycle Management
- **Milestone:** M3 (Asynchronous Evaluation Engine)
- **Component:** Backend API
- **Dependencies:** [TASK-01](./TASK-01-database-and-backend-foundation.md), [TASK-04](./TASK-04-evaluation-worker-and-queue-system.md)

---

## 2. Objective & Scope
Implement the results retrieval endpoint (`GET /api/v1/sessions/{id}/results`) designed for client polling, calculate progress statistics, aggregate overall session scores, implement the retry endpoint for failed evaluations (`POST /api/v1/answers/{id}/retry`), and provide a session deletion endpoint (`DELETE /api/v1/sessions/{id}`) to fulfill privacy and data retention guidelines.

---

## 3. Technical Requirements

### 3.1 Results Aggregation Endpoint

#### `GET /api/v1/sessions/{id}/results`
- **Response Contract (200 OK):**
  ```json
  {
    "status": "ended",
    "progress": {
      "total": 6,
      "evaluated": 4,
      "failed": 0
    },
    "overall_score": 7.2,
    "items": [
      {
        "question_id": "e4028b08-b39b-4682-8bc9-9372ef35b2e3",
        "answer_id": "97e68cf3-1577-4b72-a0f5-4f36c53e028b",
        "question": "Can you walk me through your experience designing high-throughput message pipelines using Kafka?",
        "transcript": "In our payment gateway, we ensured idempotency by storing transaction idempotency keys in Redis with a 24-hour TTL...",
        "status": "evaluated",
        "evaluation": {
          "score": 7,
          "star": {
            "situation": 2,
            "task": 1,
            "action": 2,
            "result": 1,
            "notes": "Good context, but could be clearer on the quantifiable business metrics."
          },
          "technical_depth": {
            "score": 7,
            "notes": "Solid understanding of partitioning and offsets; missed consumer group rebalancing."
          },
          "missing_points": [
            "idempotency",
            "dead-letter queue",
            "consumer group lag"
          ],
          "suggested_answer": "At Company A, we processed 50,000 events/sec. To guarantee at-least-once delivery without duplicates, we..."
        }
      },
      {
        "question_id": "c869e54d-7bc4-411a-8bb7-d8d4791a8ea9",
        "answer_id": "b188c032-612b-402a-9cb3-69024f0c4391",
        "question": "What strategies did you use to handle Redis failover or network partitioning during peak transactions?",
        "transcript": "We used Redis Sentinel and client-side retry policies...",
        "status": "pending",
        "evaluation": null
      }
    ]
  }
  ```

- **Computation Rules:**
  - `total`: Total number of questions answered in this session (`COUNT(answers.id)`).
  - `evaluated`: Number of answers where `status = 'evaluated'`.
  - `failed`: Number of answers where `status = 'failed'`.
  - `overall_score`:
    - If `evaluated + failed == total` and `total > 0`: Compute the arithmetic mean of all evaluated items rounded to 1 decimal place: `ROUND(AVG(evaluations.score), 1)`. Persist this to `sessions.overall_score`.
    - If any answers are still in `status = 'pending'`: Return `overall_score: null`.
  - Items should be ordered by question index ascending (`idx ASC`).

### 3.2 Evaluation Retry Endpoint

#### `POST /api/v1/answers/{id}/retry`
- **Request:** Empty body.
- **Response (200 OK):**
  ```json
  {
    "answer_id": "b188c032-612b-402a-9cb3-69024f0c4391",
    "status": "pending",
    "message": "Evaluation re-enqueued successfully"
  }
  ```
- **Logic:**
  1. Fetch answer by ID. If not found, return `404 NOT_FOUND`.
  2. If `status == 'evaluated'`, return `400 BAD_REQUEST` ("Answer is already evaluated").
  3. Update `answers` table: `status = 'pending'`, `attempts = 0`.
  4. Enqueue new message to Azure Storage Queue `evaluation-jobs`:
     ```json
     {
       "answer_id": "b188c032-612b-402a-9cb3-69024f0c4391",
       "session_id": "<session_id>",
       "attempt": 1
     }
     ```
  5. Return updated answer status.

### 3.3 Session Deletion Endpoint (Privacy & GDPR)

#### `DELETE /api/v1/sessions/{id}`
- **Response (204 No Content):**
- **Logic:**
  1. Fetch session by ID. If not found, return `404 NOT_FOUND`.
  2. Perform cascading deletion: `DELETE FROM sessions WHERE id = :session_id`.
  3. Foreign keys with `ON DELETE CASCADE` automatically purge associated `questions`, `answers`, and `evaluations`.

---

## 4. Implementation Steps
1. Create `app/api/v1/endpoints/results.py` and register in API router.
2. Build optimized SQL query with `LEFT JOIN` across `questions`, `answers`, and `evaluations` to retrieve all results in a single query.
3. Add Pydantic response models in `app/schemas/results.py`.
4. Implement retry handler in `app/api/v1/endpoints/answers.py`.
5. Implement delete handler in `app/api/v1/endpoints/sessions.py`.
6. Write integration tests verifying partial polling states, final score calculation, retry flows, and cascade deletions.

---

## 5. Acceptance Criteria
- [ ] `GET /results` returns partial results with `evaluation: null` for pending items without crashing.
- [ ] `progress` object correctly reports counts for `total`, `evaluated`, and `failed`.
- [ ] `overall_score` is `null` while evaluations are pending, and correctly computes the mean once all are completed.
- [ ] `POST /answers/{id}/retry` re-enqueues failed items and flips status back to `pending`.
- [ ] `DELETE /sessions/{id}` completely removes all session data and dependent tables.

# TASK-09: Security, Rate Limiting, Cost Controls & Observability

## 1. Metadata
- **Task ID:** TASK-09
- **Title:** Security Hardening, IP Rate Limiting, Cost Guardrails & Telemetry
- **Milestone:** M4 (Results Dashboard, Resilience & Polish)
- **Component:** Backend API, Azure Functions, Cloud Architecture
- **Dependencies:** [TASK-01](./TASK-01-database-and-backend-foundation.md), [TASK-03](./TASK-03-audio-recording-and-transcription-pipeline.md), [TASK-04](./TASK-04-evaluation-worker-and-queue-system.md)

---

## 2. Objective & Scope
Implement security controls, IP-based rate limiting, strict cost guardrails to guarantee $0/month baseline (or pennies LLM pay-per-use), scale-to-zero container settings, token truncation limits, and Application Insights structured logging with trace correlation.

---

## 3. Technical Requirements

### 3.1 Rate Limiting Implementation
Create `app/core/rate_limiter.py` using `slowapi` (built on `limits`):
- **Rate Limit Policies:**
  - `POST /api/v1/sessions`: Max 5 requests per hour per IP. (Prevents spamming LLM session generation).
  - `POST /api/v1/sessions/{id}/answers`: Max 30 requests per hour per IP. (Sufficient for multiple full interviews, prevents audio DDOS).
  - `GET /api/v1/sessions/{id}/results`: Max 120 requests per minute per IP. (Permits 2-second client polling intervals).
- **Rate Limit Response:** Return HTTP 429:
  ```json
  {
    "error": {
      "code": "RATE_LIMITED",
      "message": "Too many requests. Please wait a moment before trying again."
    }
  }
  ```

### 3.2 Security Hardening
- **CORS Configuration:**
  - Lock down `CORSMiddleware` in `app/main.py`.
  - Allowed Origins: Configurable via `CORS_ORIGINS` environment variable (e.g. `https://<app>.azurestaticapps.net`, `http://localhost:5173`).
  - Wildcards (`*`) strictly disallowed in production.
- **Upload Validation:**
  - Maximum upload size 10 MB enforced at the web server and FastAPI layer.
  - Magic byte / MIME type validation for audio uploads.
- **Secrets Management:**
  - Zero secrets in frontend bundle.
  - In local development: `.env` excluded via `.gitignore`.
  - In Azure Container Apps: Key Vault reference or Container App secrets.

### 3.3 Cost Control Guardrails ($0/Month Target)
1. **Azure Container Apps Configuration:**
   - Scale Rule: `minReplicas = 0`, `maxReplicas = 1`. (Scales down to 0 after 300s of inactivity, consuming 0 vCPU-seconds).
   - Resources: `0.5 vCPU` / `1.0 GiB` memory (or `1.0 vCPU` / `2.0 GiB` maximum). Fits within the monthly free grant (180,000 vCPU-seconds and 360,000 GiB-seconds free per month).
2. **Token Budget Enforcement:**
   - Enforce hard cutoff on input text prior to sending prompts to `gpt-4o-mini`:
     - Resume: Max 1,500 tokens.
     - JD: Max 1,000 tokens.
     - Candidate Transcript: Max 500 tokens (answers capped at 3 minutes of speech).
   - Truncation warning logged if input exceeds limit.
3. **Model Pinning:**
   - Restrict model deployments strictly to `gpt-4o-mini` (Azure OpenAI serverless pricing: ~$0.15 / 1M input tokens, ~$0.60 / 1M output tokens).
4. **Azure Budget Alert:**
   - Provide Azure CLI / ARM template configuration to set a **$2.00 / month** budget alert with email notification.
5. **Supabase Inactivity Mitigation:**
   - Free tier Supabase projects pause after 7 days of inactivity. Include a lightweight scheduled ping or document cold-resume instructions.

### 3.4 Structured Logging & Observability
Create `app/core/logging.py`:
- Use `structlog` or Python `logging` with JSON formatting:
  ```json
  {
    "timestamp": "2026-10-04T12:00:00Z",
    "level": "INFO",
    "session_id": "a3bb101a-8269-4a4c-9f8b-201efb5e5a2b",
    "answer_id": "97e68cf3-1577-4b72-a0f5-4f36c53e028b",
    "event": "transcription_completed",
    "duration_seconds": 45.2,
    "transcription_time_ms": 1420,
    "tokens_used": { "prompt": 450, "completion": 85 }
  }
  ```
- Integrate Azure Application Insights SDK (`opencensus-ext-azure` or OpenTelemetry Azure exporter) for distributed tracing across FastAPI and the Azure Functions background worker.

---

## 4. Implementation Steps
1. Install and configure `slowapi` in FastAPI backend.
2. Add token calculation utility using `tiktoken` to enforce prompt length caps.
3. Implement JSON logging formatter with `session_id` and `answer_id` context injection.
4. Prepare Azure ARM/Bicep template configuring scale-to-zero Container App and consumption Function App.
5. Setup Azure Cost Management budget alert script.

---

## 5. Acceptance Criteria
- [ ] Exceeding 5 session creations in 1 hour returns `429 RATE_LIMITED`.
- [ ] Uploading audio files larger than 10 MB returns `413 PAYLOAD_TOO_LARGE`.
- [ ] CORS rejects requests originating from unauthorized external domains.
- [ ] Container App scales to 0 replicas during idle periods.
- [ ] Log outputs contain correlated `session_id` and timing metrics for transcription and LLM inference.

# TASK-10: Testing Strategy, Quality Benchmarks & Deployment Pipeline

## 1. Metadata
- **Task ID:** TASK-10
- **Title:** Comprehensive Test Suites, STT Jargon Benchmarks & Azure CI/CD Pipelines
- **Milestone:** M5 (Polish, Testing & Deployment)
- **Component:** Test Automation & DevOps / Infrastructure
- **Dependencies:** All previous tasks ([TASK-01](./TASK-01-database-and-backend-foundation.md) through [TASK-09](./TASK-09-security-rate-limiting-and-cost-controls.md))

---

## 2. Objective & Scope
Implement the full testing pyramid specified in Section 12: unit tests, integration tests against local emulators, a specialized Word Error Rate (WER) jargon benchmark for `faster-whisper`, Playwright end-to-end tests using virtual media streams, and automated CI/CD deployment pipelines targeting Azure Static Web Apps, Azure Container Apps, and Azure Functions.

---

## 3. Technical Requirements

### 3.1 Test Automation Matrix

```text
tests/
├── unit/
│   ├── test_document_parser.py
│   ├── test_prompt_builders.py
│   ├── test_score_aggregation.py
│   └── test_schema_validation.py
├── integration/
│   ├── test_sessions_api.py
│   ├── test_answers_pipeline.py
│   ├── test_results_polling.py
│   └── test_worker_execution.py
├── benchmarks/
│   ├── test_transcription_jargon.py
│   └── audio_fixtures/
│       ├── sample_distributed_systems.wav
│       └── sample_data_pipelines.wav
└── e2e/
    ├── playwright.config.ts
    └── specs/
        └── interview_flow.spec.ts
```

#### 1. Unit Tests (`pytest`)
- **Prompt Builders:** Ensure `exclude_topics` and `include_topics` formatting rules are strictly injected.
- **Score Aggregation:** Verify arithmetic rounding and edge cases (e.g. 0 answered questions, partial failures, single question sessions).
- **Schema Validation:** Verify Pydantic validation handles valid, malformed, and boundary LLM responses.

#### 2. Integration Tests
- **API Tests:** Run FastAPI test client against a test Postgres container or Supabase test schema.
- **Mock LLM:** Use stubbed Azure OpenAI responses to ensure fast and deterministic execution without incurring token costs.
- **Azurite Integration:** Verify worker reads messages from local Azurite Azure Storage Queue emulator, processes the task, and commits evaluation records.

#### 3. Transcription Jargon Accuracy Benchmark
Create `tests/benchmarks/test_transcription_jargon.py`:
- Provide a dataset of 5 short recorded audio clips containing dense technical terms:
  - Clip 1: `"We deployed an Envoy service mesh with mutual TLS and gRPC streaming."`
  - Clip 2: `"We configured Apache Kafka with idempotence enabled and a Dead Letter Queue."`
  - Clip 3: `"To prevent race conditions, we used Redis Redlock and optimistic locking."`
- Measure Word Error Rate (WER) using `jiwer`.
- Assert that prompt-seeded `faster-whisper` `base.en` achieves 0% error rate on the designated domain keywords.

#### 4. End-to-End (E2E) Browser Tests (`Playwright`)
Create `tests/e2e/specs/interview_flow.spec.ts`:
- Configure Chromium with virtual media flags:
  ```typescript
  // playwright.config.ts
  use: {
    launchOptions: {
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        '--use-file-for-fake-audio-capture=tests/e2e/fixtures/test_voice.wav'
      ]
    }
  }
  ```
- Test sequence:
  1. Visit landing page.
  2. Paste resume and JD text, select "Senior", add topic tags, and click "Start Interview".
  3. Verify transition to Interview Screen with Question 1 displayed.
  4. Click "Record", verify audio indicator pulses, wait 3 seconds, click "Stop Recording".
  5. Click "Submit Answer" and verify transition to Question 2.
  6. Click "End Interview Early" and confirm.
  7. Verify Results Dashboard loads, progress bar updates, and STAR cards render properly.

---

### 3.2 CI/CD Deployment Pipelines (GitHub Actions)

#### 1. Frontend Pipeline (`.github/workflows/frontend-deploy.yml`)
- Trigger on push to `main` for `src/frontend/**`.
- Build Vite React application.
- Deploy to **Azure Static Web Apps** using `Azure/static-web-apps-deploy@v1` (Free tier).

#### 2. Backend Container Pipeline (`.github/workflows/backend-deploy.yml`)
- Trigger on push to `main` for `src/backend/**`.
- Build multi-stage Docker image:
  ```dockerfile
  FROM python:3.11-slim
  RUN apt-get update && apt-get install -y ffmpeg libgomp1 && rm -rf /var/lib/apt/lists/*
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY app ./app
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
  ```
- Push image to GitHub Container Registry (GHCR) or Azure Container Registry (ACR).
- Deploy to **Azure Container Apps** with scale-to-zero setting (`min-replicas=0`, `max-replicas=1`).

#### 3. Worker Function Pipeline (`.github/workflows/worker-deploy.yml`)
- Trigger on push to `main` for `src/worker/**`.
- Package and deploy to **Azure Functions** (Consumption plan) using `azure/functions-action@v1`.

---

## 4. Implementation Steps
1. Setup `pytest` environment with `pytest-asyncio`, `httpx`, and `jiwer`.
2. Write unit tests for business logic and scoring algorithms.
3. Write Azurite queue integration test suite.
4. Add technical audio benchmark files and run accuracy assertions.
5. Setup Playwright configuration with media stream emulation.
6. Author GitHub Actions workflow YAML files for frontend, backend, and worker.

---

## 5. Acceptance Criteria
- [ ] All unit and integration test suites pass in CI (`pytest tests/`).
- [ ] Jargon benchmark passes with 0% error on target technical terms.
- [ ] Playwright E2E test executes the full user journey headlessly without audio hardware.
- [ ] GitHub Actions workflows build and deploy frontend to Azure Static Web Apps, backend to Azure Container Apps, and worker to Azure Functions.

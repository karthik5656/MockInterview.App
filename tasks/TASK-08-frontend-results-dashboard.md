# TASK-08: Results Dashboard, Scoring & Critique UI

## 1. Metadata
- **Task ID:** TASK-08
- **Title:** Results Dashboard, Polling Engine, STAR Critique & Retry UI
- **Milestone:** M4 (Results Dashboard, Resilience & Polish)
- **Component:** Frontend (React / Tailwind CSS)
- **Dependencies:** [TASK-05](./TASK-05-results-aggregation-and-polling-api.md), [TASK-07](./TASK-07-frontend-interview-interface.md)

---

## 2. Objective & Scope
Implement the **Results Dashboard** (Screen 3 of 3) displaying session performance, background evaluation polling with exponential backoff, overall session score, granular per-question STAR critiques, technical depth evaluation, missing Job Description keywords, exemplary suggested answers, retry buttons for failed evaluations, and privacy session deletion.

---

## 3. Technical Requirements

### 3.1 Polling Engine Hook (`useResultsPolling`)
Create `src/frontend/hooks/useResultsPolling.ts`:
- Poll `GET /api/v1/sessions/{id}/results`.
- Initial polling interval: `2000ms`.
- After 30 seconds of pending evaluations: increase backoff interval to `4000ms`.
- Condition to stop polling:
  ```typescript
  const isComplete = results && (results.progress.evaluated + results.progress.failed === results.progress.total);
  ```
- Gracefully handle network drops with retry without terminating the polling loop.

### 3.2 Dashboard Screen Components (`ResultsPage.tsx`)

```text
src/frontend/components/results/
├── ScoreOverviewCard.tsx
├── EvaluationProgressBar.tsx
├── QuestionResultCard.tsx
├── StarBreakdownView.tsx
├── TechnicalDepthView.tsx
├── MissingPointsList.tsx
├── SuggestedAnswerView.tsx
└── RetryItemButton.tsx
```

#### 1. Header & Progress Banner
- Displays session status:
  - If pending: Animated progress bar showing `"Analyzing your responses: {evaluated} of {total} completed"`.
  - If complete: Green badge `"Evaluation Complete"`.
- Overall Score Card:
  - Large circular radial meter displaying score `/ 10` (e.g. `7.2 / 10`).
  - Score badge changes color:
    - `>= 8.0`: Emerald green (Strong Hire)
    - `6.0 - 7.9`: Blue/Amber (Hire / Needs Polish)
    - `< 6.0`: Rose/Red (Needs Significant Preparation)
  - While pending, displays `"Calculating final score..."` with a skeleton pulse.

#### 2. Per-Question Evaluation Accordion / Cards
For each question item in `results.items`:
- **Header:** Question Index, Question Text, Status Badge (`Evaluated` / `Evaluating...` / `Evaluation Failed`), Item Score `/10`.
- **Transcript Section:**
  - Collapsible box displaying the candidate's exact transcribed answer.
- **STAR Methodology Breakdown:**
  - Visual meter or 4 progress gauges:
    - **S**ituation: `2 / 2`
    - **T**ask: `1 / 2`
    - **A**ction: `2 / 3`
    - **R**esult: `1 / 3`
  - Feedback note highlighting where the structure was strong or lacked quantification.
- **Technical Depth Review:**
  - Depth Score `/10`.
  - Detailed architectural feedback and trade-off analysis critique.
- **Missing JD Points & Keywords:**
  - Red/Amber tag chips representing critical keywords from the JD that the candidate omitted (e.g. `["idempotency", "circuit breaker", "dead-letter queue"]`).
- **Exemplary Suggested Rewrite:**
  - A formatted, side-by-side or blockquote model answer showing how a Staff-level candidate would answer the prompt concisely using STAR structure.

#### 3. Failure & Retry Handling (FR-9)
- If an item has `status: "failed"`:
  - Display error alert box: `"Evaluation timed out or failed to process."`
  - Display "Retry Evaluation" button.
  - Clicking triggers `POST /api/v1/answers/{id}/retry`.
  - State flips back to `pending`, resuming polling automatically.

#### 4. Session Actions
- "Start New Interview": Clears current session state from memory and `sessionStorage`, redirects to `/`.
- "Delete Session & Data": Confirmation dialog triggering `DELETE /api/v1/sessions/{id}` to permanently purge resume, JD, transcripts, and evaluation scores from the database.

---

## 4. Implementation Steps
1. Create `useResultsPolling.ts` hook.
2. Build `ScoreOverviewCard.tsx` with circular score meter.
3. Build `QuestionResultCard.tsx` encapsulating STAR gauges, technical depth, missing tags, and suggested answers.
4. Implement retry mechanism connected to the backend retry endpoint.
5. Implement session deletion and data wipe confirmation modal.
6. Assemble `ResultsPage.tsx` with responsive layout and empty/loading states.

---

## 5. Acceptance Criteria
- [ ] Dashboard starts polling immediately upon entry and renders progress updates smoothly.
- [ ] Questions transition from skeleton loading to evaluated state dynamically as background worker commits evaluations.
- [ ] Polling terminates automatically once all items reach terminal state (`evaluated` or `failed`).
- [ ] Overall score calculates and displays accurately once all evaluations complete.
- [ ] Clicking "Retry" on a failed evaluation re-enqueues the item and resumes the polling animation.
- [ ] Clicking "Delete Session" purges data from database and redirects user cleanly to home page.

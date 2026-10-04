# TASK-06: Frontend Core Setup & Session Configuration Screen

## 1. Metadata
- **Task ID:** TASK-06
- **Title:** Frontend Setup, Architecture & Session Configuration Screen
- **Milestone:** M1 (Foundation & Core Setup)
- **Component:** Frontend (React / Vite / Tailwind CSS)
- **Dependencies:** [TASK-01](./TASK-01-database-and-backend-foundation.md), [TASK-02](./TASK-02-session-management-and-question-generation.md)

---

## 2. Objective & Scope
Bootstrap the frontend client application using React, Vite, TypeScript, and Tailwind CSS. Implement global state management, API service layer, resilient `sessionStorage` sync, and build the initial **Session Configuration Screen** (FR-1, FR-2) allowing candidates to provide their Resume, Job Description, difficulty tier, and topic preferences.

---

## 3. Technical Requirements

### 3.1 Project Structure & Tooling
Scaffold the frontend under `src/frontend`:
```text
src/frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── src/
│   ├── api/
│   │   ├── client.ts
│   │   ├── sessions.ts
│   │   └── types.ts
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.tsx
│   │   │   ├── Dropzone.tsx
│   │   │   ├── TagInput.tsx
│   │   │   └── Alert.tsx
│   │   ├── config/
│   │   │   ├── DifficultySelector.tsx
│   │   │   └── DocumentInputGroup.tsx
│   │   └── layout/
│   │       ├── Header.tsx
│   │       └── Layout.tsx
│   ├── context/
│   │   └── InterviewContext.tsx
│   ├── hooks/
│   │   └── useSessionStorage.ts
│   ├── pages/
│   │   ├── ConfigurePage.tsx
│   │   ├── InterviewPage.tsx
│   │   └── ResultsPage.tsx
│   ├── App.tsx
│   └── main.tsx
```

### 3.2 Global State & Persistence
Create `src/frontend/context/InterviewContext.tsx`:
- State contract:
  ```typescript
  interface SessionState {
    sessionId: string | null;
    currentQuestion: {
      id: string;
      index: number;
      text: string;
    } | null;
    isEnded: boolean;
    config: {
      difficulty: 'junior' | 'mid' | 'senior' | 'staff';
      includeTopics: string[];
      excludeTopics: string[];
      maxQuestions: number;
    } | null;
  }
  ```
- Persist `sessionId` and current question state to `sessionStorage` on every state mutation so an accidental browser refresh retains the active session.

### 3.3 Configuration Screen Design & Features (`ConfigurePage.tsx`)

#### 1. Document Inputs (FR-1)
- **Resume Section:**
  - Tab 1: "Upload File" (Drag-and-drop support for `.pdf`, `.docx`, `.txt` up to 5 MB).
  - Tab 2: "Paste Text" (Rich textarea with character count indicator).
- **Job Description Section:**
  - Tab 1: "Upload File" or Tab 2: "Paste Text".
- Client-side extraction or pass directly to backend parsing endpoint.

#### 2. Interview Customization (FR-2)
- **Difficulty Tier Selector:**
  - 4 distinct radio cards: Junior, Mid, Senior, Staff.
  - Visual badge with brief description (e.g. Senior: "System design, architectural trade-offs, and failure scenarios").
- **Topic Filters:**
  - `Include Topics` (e.g. "Kafka", "PostgreSQL", "Idempotency", "System Design"): Enter tag chips.
  - `Exclude Topics` (e.g. "Frontend", "CSS", "Mobile"): Negative filter chips.
- **Max Questions:**
  - Range slider or select dropdown from 3 to 15 (default: 10).

#### 3. Start Interview Action
- "Start Interview" button.
- Triggers validation:
  - Resume length >= 50 chars or valid file attached.
  - JD length >= 50 chars or valid file attached.
- Displays loading spinner and "Generating tailored questions..." status.
- Upon 201 response, saves session ID and question 1 to context and navigates to `/interview`.

---

## 4. Implementation Steps
1. Initialize Vite React TypeScript template in `src/frontend` with Tailwind CSS and Lucide React icons.
2. Setup Axios or `fetch` wrapper in `src/frontend/api/client.ts` with error handling interceptors matching the backend error schema `{ error: { code, message } }`.
3. Build reusable UI components: `Button`, `Dropzone`, `TagInput`, and `RadioCardGroup`.
4. Implement `InterviewContext` with `sessionStorage` fallback.
5. Build `ConfigurePage.tsx` with responsive layout and input validation.
6. Connect form submit action to `POST /api/v1/sessions` API endpoint.

---

## 5. Acceptance Criteria
- [ ] Dragging and dropping a PDF or DOCX file accurately stages it for upload.
- [ ] Users can paste text directly into Resume and JD text fields.
- [ ] Topic include/exclude tags can be added and removed intuitively via keyboard (Enter/Backspace).
- [ ] Clicking "Start Interview" with invalid inputs shows user-friendly validation warnings.
- [ ] On successful submission, API receives correct payload, and user transitions to the Interview screen with Question 1 loaded.
- [ ] Page reload preserves session state without resetting the user back to the config page.

# TASK-07: Voice Recording & Interactive Interview Screen

## 1. Metadata
- **Task ID:** TASK-07
- **Title:** Voice Recording Component, Interactive Interview Screen & Text Fallback
- **Milestone:** M2 (Voice Pipeline & Audio Processing)
- **Component:** Frontend (React / Web Audio API / MediaRecorder)
- **Dependencies:** [TASK-03](./TASK-03-audio-recording-and-transcription-pipeline.md), [TASK-06](./TASK-06-frontend-core-and-configuration-screen.md)

---

## 2. Objective & Scope
Implement the interactive **Interview Screen** (Screen 2 of 3), featuring a voice recording interface powered by `MediaRecorder` (`audio/webm;codecs=opus`), live audio level visualizer (VU-meter), strict 3-minute answer countdown, transcript preview and re-record capability (FR-10), keyboard navigation accessibility, microphone error recovery with text fallback mode, and session progression handling.

---

## 3. Technical Requirements

### 3.1 Voice Recorder Architecture (`useVoiceRecorder` Hook)
Create `src/frontend/hooks/useVoiceRecorder.ts`:
- **Audio Capture:**
  - Request permission via `navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })`.
  - Handle permission denial gracefully by toggling fallback mode.
- **MediaRecorder Configuration:**
  - Detect best supported MIME type: `audio/webm;codecs=opus` -> `audio/webm` -> `audio/ogg;codecs=opus` -> `audio/mp4`.
  - Collect audio chunks into an array on `ondataavailable`.
  - Create audio blob on `onstop`.
- **Audio Level Metering (VU Meter):**
  - Connect audio stream to `AudioContext` and `AnalyserNode`.
  - Sample frequency data via `requestAnimationFrame` to calculate root mean square (RMS) amplitude (0% to 100%).
  - Expose `volumeLevel` for dynamic visual pulsation.
- **Time Limits:**
  - Hard cap at 3 minutes (180 seconds).
  - Provide remaining seconds countdown; automatically stop recording when timer hits 00:00.

### 3.2 Interview Screen Components (`InterviewPage.tsx`)

```text
src/frontend/components/interview/
├── QuestionDisplay.tsx
├── AudioVisualizer.tsx
├── RecordingControls.tsx
├── TranscriptPreviewModal.tsx
├── TextFallbackInput.tsx
└── EndInterviewModal.tsx
```

#### 1. Question Display (`QuestionDisplay.tsx`)
- Display badge: `"Question {index} of {maxQuestions}"`.
- Large, high-contrast question prompt.
- Optional question audio readout button using browser `window.speechSynthesis` (free, client-side TTS).

#### 2. Recording Controls & Visualizer
- **Inactive State:** Large "Start Answering (Voice)" button + "Switch to Text Input" secondary link.
- **Recording State:**
  - Glowing red pulse indicator + animated waveform / volume bar.
  - Active countdown timer: `02:45 / 03:00`.
  - "Stop Recording" button.
- **Recorded State (Review & Submit - FR-10):**
  - "Listen Back" audio player component to verify recording clarity.
  - "Re-record" button (discards blob and resets recording timer).
  - "Submit Answer" primary button.

#### 3. Keyboard Accessibility & Shortcuts
- Spacebar / Enter triggers Start/Stop recording when focused on recording widget.
- Escape cancels active recording.
- Clear ARIA labels for recording status (`aria-live="polite"`).

#### 4. Text Fallback Mode
- Activated if:
  - User explicitly clicks "Type your answer instead".
  - Browser mic permission is denied or unvailable (e.g. non-HTTPS, missing hardware).
- Provides rich textarea with character count and "Submit Answer" button.

### 3.3 Answer Submission Flow
1. User clicks "Submit Answer".
2. UI enters loading state: "Transcribing audio and analyzing context... (takes 2-4 seconds)".
3. API call to `POST /api/v1/sessions/{id}/answers` with `multipart/form-data` containing audio blob or text string.
4. Response Handling:
   - If error (e.g. `EMPTY_AUDIO`): Show warning banner ("No clear speech detected. Please re-record your answer") and remain on current question.
   - If success:
     - If `done === true` or `next_question === null`: Automatically redirect to `/results/{sessionId}`.
     - Else: Update `currentQuestion` in context to `next_question`, reset recorder state, and display question index increment.
5. "Finish Interview Early" action:
   - Displays confirmation dialog.
   - On confirmation, calls `POST /api/v1/sessions/{id}/end` and redirects immediately to Results.

---

## 4. Implementation Steps
1. Implement `useVoiceRecorder.ts` and `useAudioVisualizer.ts` custom React hooks.
2. Build `AudioVisualizer.tsx` rendering animated canvas or multi-bar SVG volume indicators.
3. Build `RecordingControls.tsx` with start/stop/rerecord states and timer countdown.
4. Integrate `TextFallbackInput.tsx` toggleable view.
5. Implement `InterviewPage.tsx` coordinating state transitions and API communication.
6. Test microphone permissions in Chromium and Firefox.

---

## 5. Acceptance Criteria
- [ ] Clicking record activates microphone and displays real-time VU-meter volume reactivity.
- [ ] Timer stops recording automatically upon reaching 3 minutes.
- [ ] User can play back the recorded audio clip and choose to re-record prior to final submission.
- [ ] Denying browser microphone permissions seamlessly transitions the view to Text Fallback mode with clear instructions.
- [ ] Submitting an answer transitions cleanly to the next question in under 5 seconds without UI flickering.
- [ ] Ending the interview early triggers `POST /sessions/{id}/end` and navigates to the results dashboard.

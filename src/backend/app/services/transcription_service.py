import asyncio
import re
from typing import Optional, Tuple
from faster_whisper import WhisperModel

from app.core.logging import logger

# Recognized silence or hallucination tokens generated on silent audio
SILENCE_TOKENS = {
    "",
    "[blank_audio]",
    "blank_audio",
    "thank you.",
    "thank you",
    "thank you for watching.",
    "thank you for watching",
    "you",
    "you.",
    "[silence]",
    "silence",
    "[music]",
    "music",
    "(silence)",
    "(bell rings)",
    "(applause)",
}


class TranscriptionService:
    """In-process Speech-to-Text service using faster-whisper base.en int8 CPU."""

    def __init__(self, model_size: str = "base.en", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Optional[WhisperModel] = None

    def load_model(self) -> None:
        """Loads WhisperModel in memory once during application startup lifespan."""
        if self._model is None:
            logger.info(
                "Loading faster-whisper model '%s' (device=%s, compute_type=%s)...",
                self.model_size,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model loaded successfully.")

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            self.load_model()
        return self._model

    def _transcribe_sync(
        self,
        audio_file_path: str,
        initial_prompt: Optional[str] = None,
    ) -> Tuple[str, float]:
        """Synchronous CPU-bound transcription method."""
        kwargs = {
            "beam_size": 5,
            "vad_filter": True,
        }
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt

        segments, info = self.model.transcribe(audio_file_path, **kwargs)

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        transcript = " ".join(part for part in text_parts if part).strip()
        duration = float(info.duration) if info and info.duration is not None else 0.0

        return transcript, round(duration, 2)

    async def transcribe(
        self,
        audio_file_path: str,
        initial_prompt: Optional[str] = None,
    ) -> Tuple[str, float]:
        """Offloads CPU-bound transcription to a worker thread to keep the event loop non-blocking."""
        return await asyncio.to_thread(self._transcribe_sync, audio_file_path, initial_prompt)

    @staticmethod
    def is_silent_or_empty(text: Optional[str]) -> bool:
        """Determines if the transcribed text is empty, whitespace-only, or composed solely of silence tokens."""
        if not text:
            return True
        cleaned = text.strip()
        if not cleaned:
            return True

        normalized = cleaned.lower()
        if normalized in SILENCE_TOKENS:
            return True

        # Remove surrounding brackets/parens/punctuation to check token
        stripped_punct = re.sub(r"^[\[\(\s\.\,\!\?]+|[\]\)\s\.\,\!\?]+$", "", normalized)
        if stripped_punct in SILENCE_TOKENS or not stripped_punct:
            return True

        return False


transcription_service = TranscriptionService()

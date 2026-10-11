import json
from typing import Optional
from azure.storage.queue import QueueClient, TextBase64EncodePolicy
from azure.core.exceptions import ResourceExistsError

from app.core.config import settings
from app.core.logging import logger


class QueueService:
    """Service to publish evaluation jobs to Azure Storage Queue."""

    def __init__(self):
        self._queue_client: Optional[QueueClient] = None
        self._disabled: bool = False

    def _is_placeholder(self) -> bool:
        conn = (settings.AZURE_STORAGE_CONNECTION_STRING or "").strip()
        return not conn or "AccountName=..." in conn or "your-storage" in conn.lower()

    def get_client(self) -> Optional[QueueClient]:
        if self._queue_client is None and not self._disabled:
            if self._is_placeholder():
                logger.warning(
                    "AZURE_STORAGE_CONNECTION_STRING is not configured or is placeholder. Queue dispatch will be simulated."
                )
                self._disabled = True
                return None

            try:
                self._queue_client = QueueClient.from_connection_string(
                    conn_str=settings.AZURE_STORAGE_CONNECTION_STRING,
                    queue_name=settings.EVALUATION_QUEUE_NAME,
                    message_encode_policy=TextBase64EncodePolicy(),
                )
                try:
                    self._queue_client.create_queue()
                    logger.info("Ensured Azure Storage Queue '%s' exists.", settings.EVALUATION_QUEUE_NAME)
                except ResourceExistsError:
                    pass
            except Exception as exc:
                logger.warning(
                    "Failed to initialize Azure Storage Queue client: %s. Queue dispatch will be simulated.",
                    str(exc),
                )
                self._disabled = True
                return None

        return self._queue_client

    def send_evaluation_message(self, answer_id: str, session_id: str, attempt: int = 1) -> bool:
        """Sends an evaluation job message to the evaluation-jobs queue."""
        payload = {
            "answer_id": str(answer_id),
            "session_id": str(session_id),
            "attempt": attempt,
        }
        message_str = json.dumps(payload)

        client = self.get_client()
        if client is None:
            logger.info("Simulated queue dispatch for answer %s: %s", answer_id, message_str)
            return True

        try:
            client.send_message(message_str)
            logger.info("Enqueued evaluation job for answer %s to queue '%s'", answer_id, settings.EVALUATION_QUEUE_NAME)
            return True
        except Exception as exc:
            logger.error("Failed to enqueue evaluation job for answer %s: %s", answer_id, str(exc))
            # Don't fail the answer submission if queue publish fails; background retry or polling can recover
            return False


queue_service = QueueService()

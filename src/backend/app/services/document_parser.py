import io
import re
from typing import Optional
from fastapi import UploadFile
from pypdf import PdfReader
from docx import Document
from app.api.errors import BadInputException


class DocumentParser:
    """Service to parse, sanitize, and truncate resumes and job descriptions."""

    RESUME_MAX_WORDS: int = 2500
    JD_MAX_WORDS: int = 2000

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitizes extracted text by removing null bytes, normalizing whitespace,

        and trimming repeated line breaks.
        """
        if not text:
            return ""

        # Remove null characters
        text = text.replace("\x00", "")

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Strip page number headers/footers like 'Page 1 of 5' or '-- 1 --'
        text = re.sub(r"(?i)\bpage\s+\d+\s+(?:of|\/)\s+\d+\b", "", text)
        text = re.sub(r"^\s*--\s*\d+\s*--\s*$", "", text, flags=re.MULTILINE)

        # Replace excessive whitespace in individual lines
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

        # Collapse multiple blank lines into at most two newlines
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @classmethod
    def truncate_words(cls, text: str, max_words: int) -> str:
        """Truncates text to a maximum word count to protect LLM context quotas."""
        if not text:
            return ""
        words = text.split()
        if len(words) > max_words:
            return " ".join(words[:max_words])
        return text

    @classmethod
    def truncate_resume(cls, text: str) -> str:
        """Applies resume token budget guard (max 2,500 words)."""
        return cls.truncate_words(cls.sanitize_text(text), cls.RESUME_MAX_WORDS)

    @classmethod
    def truncate_jd(cls, text: str) -> str:
        """Applies job description token budget guard (max 2,000 words)."""
        return cls.truncate_words(cls.sanitize_text(text), cls.JD_MAX_WORDS)

    @classmethod
    def extract_from_pdf(cls, content: bytes) -> str:
        """Extracts text from PDF binary content using pypdf."""
        try:
            reader = PdfReader(io.BytesIO(content))
            extracted_pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_pages.append(text)
            return cls.sanitize_text("\n\n".join(extracted_pages))
        except Exception as exc:
            raise BadInputException(f"Failed to parse PDF document: {str(exc)}") from exc

    @classmethod
    def extract_from_docx(cls, content: bytes) -> str:
        """Extracts text from DOCX binary content using python-docx."""
        try:
            doc = Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    cell_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cell_texts:
                        paragraphs.append(" | ".join(cell_texts))
            return cls.sanitize_text("\n\n".join(paragraphs))
        except Exception as exc:
            raise BadInputException(f"Failed to parse DOCX document: {str(exc)}") from exc

    @classmethod
    def extract_from_plain_text(cls, content: bytes) -> str:
        """Decodes UTF-8 / plain text bytes."""
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except Exception as exc:
                raise BadInputException(f"Failed to decode plain text document: {str(exc)}") from exc
        return cls.sanitize_text(text)

    @classmethod
    def parse_bytes(
        cls,
        content: bytes,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """Detects document type and extracts text from binary content."""
        if not content:
            raise BadInputException("Uploaded document is empty")

        filename_lower = (filename or "").lower()
        ct_lower = (content_type or "").lower()

        if filename_lower.endswith(".pdf") or "application/pdf" in ct_lower:
            return cls.extract_from_pdf(content)
        elif (
            filename_lower.endswith(".docx")
            or "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ct_lower
        ):
            return cls.extract_from_docx(content)
        elif (
            filename_lower.endswith(".txt")
            or filename_lower.endswith(".md")
            or "text/plain" in ct_lower
            or "text/markdown" in ct_lower
        ):
            return cls.extract_from_plain_text(content)
        else:
            # Fallback: attempt plain text decode first, then pdf
            try:
                return cls.extract_from_plain_text(content)
            except Exception:
                raise BadInputException(
                    f"Unsupported file format for '{filename or 'uploaded file'}'. "
                    "Only PDF, DOCX, and plain text files are supported."
                )

    @classmethod
    async def parse_upload_file(cls, file: UploadFile) -> str:
        """Parses a FastAPI UploadFile into sanitized text."""
        content = await file.read()
        return cls.parse_bytes(
            content=content,
            filename=file.filename,
            content_type=file.content_type,
        )
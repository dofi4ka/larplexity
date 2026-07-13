from __future__ import annotations

import re
from pathlib import Path

import structlog
from aiogram.types import Document as TelegramDocument

from config import Settings
from services.memory_service import MemoryService
from storage.repositories.documents import DocumentRepository

log = structlog.get_logger(__name__)


class IngestService:
    def __init__(
        self,
        settings: Settings,
        documents: DocumentRepository,
        memory: MemoryService,
    ) -> None:
        self.settings = settings
        self.documents = documents
        self.memory = memory

    def is_allowed(self, filename: str, file_size: int | None) -> tuple[bool, str]:
        suffix = Path(filename).suffix.lower()
        if suffix not in self.settings.allowed_upload_extensions:
            return False, f"Unsupported file type: {suffix or '(none)'}"
        if file_size is not None and file_size > self.settings.max_upload_bytes:
            return False, "File is too large"
        return True, ""

    async def ingest_telegram_document(
        self,
        *,
        user_id: int,
        chat_id: int,
        tg_document: TelegramDocument,
        local_path: Path,
    ) -> tuple[int, int]:
        ok, reason = self.is_allowed(tg_document.file_name or local_path.name, tg_document.file_size)
        if not ok:
            raise ValueError(reason)

        # Safety: only write under configured uploads directory.
        uploads = self.settings.uploads_dir.resolve()
        resolved = local_path.resolve()
        if uploads not in resolved.parents and resolved != uploads:
            raise PermissionError("Refusing to write outside uploads directory")

        doc = await self.documents.create(
            user_id=user_id,
            chat_id=chat_id,
            filename=tg_document.file_name or local_path.name,
            mime_type=tg_document.mime_type,
            storage_path=str(resolved),
            byte_size=int(tg_document.file_size or resolved.stat().st_size),
            status="processing",
        )

        try:
            text = self._extract_text(resolved)
            chunk_count = await self.memory.index_document(
                user_id=user_id,
                chat_id=chat_id,
                document_id=doc.id,
                content=text,
            )
            await self.documents.update_status(doc.id, "ready")
            log.info("document_ingested", document_id=doc.id, chunks=chunk_count)
            return doc.id, chunk_count
        except Exception:
            await self.documents.update_status(doc.id, "failed")
            raise

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf(path)
        # Text-like formats only — no shell / executable handling.
        raw = path.read_bytes()
        if b"\x00" in raw[:2048]:
            raise ValueError("Binary files are not supported")
        text = raw.decode("utf-8", errors="replace")
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            raise ValueError("File is empty")
        return text

    def _extract_pdf(self, path: Path) -> str:
        # Lightweight PDF text extraction without extra heavy deps:
        # try pypdf if present; otherwise fail clearly.
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:
            raise ValueError(
                "PDF support requires pypdf. Install it or send a text file."
            ) from exc
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages[:50]:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        if not text:
            raise ValueError("Could not extract text from PDF")
        return text

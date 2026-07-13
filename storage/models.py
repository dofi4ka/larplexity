from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class User:
    id: int
    telegram_id: int
    username: str | None
    display_name: str | None
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Chat:
    id: int
    user_id: int
    title: str
    summary: str | None
    is_archived: bool
    created_at: str
    updated_at: str
    last_message_at: str | None


@dataclass(slots=True)
class Message:
    id: int
    chat_id: int
    role: str
    content: str
    telegram_message_id: int | None
    metadata_json: str | None
    created_at: str


@dataclass(slots=True)
class MessageChunk:
    id: int
    message_id: int
    chat_id: int
    user_id: int
    chunk_index: int
    content: str
    embedding_json: str | None
    embedding_model: str | None
    token_count: int | None
    created_at: str


@dataclass(slots=True)
class Document:
    id: int
    user_id: int
    chat_id: int | None
    filename: str
    mime_type: str | None
    storage_path: str
    byte_size: int
    status: str
    created_at: str


@dataclass(slots=True)
class DocumentChunk:
    id: int
    document_id: int
    user_id: int
    chat_id: int | None
    chunk_index: int
    content: str
    embedding_json: str | None
    embedding_model: str | None
    token_count: int | None
    created_at: str


@dataclass(slots=True)
class Citation:
    id: int
    chat_id: int
    message_id: int | None
    research_run_id: int | None
    source_type: str
    source_url: str | None
    title: str | None
    snippet: str | None
    metadata_json: str | None
    created_at: str


@dataclass(slots=True)
class ResearchRun:
    id: int
    chat_id: int
    user_id: int
    query: str
    status: str
    queries_json: str | None
    sources_json: str | None
    facts_json: str | None
    conflicts_json: str | None
    answer: str | None
    uncertainty_notes: str | None
    created_at: str
    completed_at: str | None


@dataclass(slots=True)
class RetrievedChunk:
    source: str
    content: str
    score: float
    chat_id: int | None = None
    message_id: int | None = None
    document_id: int | None = None
    title: str | None = None
    metadata: dict[str, Any] | None = None


def utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

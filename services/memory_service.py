from __future__ import annotations

from config import Settings
from services.embeddings import (
    EMBEDDING_MODEL,
    chunk_text,
    cosine_similarity,
    embed_text,
    embedding_from_json,
    embedding_to_json,
    estimate_tokens,
)
from storage.models import RetrievedChunk
from storage.repositories.chats import ChatRepository
from storage.repositories.documents import DocumentRepository
from storage.repositories.messages import MessageRepository


class MemoryService:
    def __init__(
        self,
        settings: Settings,
        messages: MessageRepository,
        documents: DocumentRepository,
        chats: ChatRepository,
    ) -> None:
        self.settings = settings
        self.messages = messages
        self.documents = documents
        self.chats = chats

    async def index_message(
        self,
        *,
        user_id: int,
        chat_id: int,
        message_id: int,
        content: str,
    ) -> None:
        chunks = chunk_text(
            content,
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
        )
        payload: list[tuple[int, str, str | None, str | None, int | None]] = []
        for idx, chunk in enumerate(chunks):
            vec = embed_text(chunk)
            payload.append(
                (
                    idx,
                    chunk,
                    embedding_to_json(vec),
                    EMBEDDING_MODEL,
                    estimate_tokens(chunk),
                )
            )
        if payload:
            await self.messages.add_chunks(
                message_id=message_id,
                chat_id=chat_id,
                user_id=user_id,
                chunks=payload,
            )

    async def index_document(
        self,
        *,
        user_id: int,
        chat_id: int | None,
        document_id: int,
        content: str,
    ) -> int:
        chunks = chunk_text(
            content,
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
        )
        payload: list[tuple[int, str, str | None, str | None, int | None]] = []
        for idx, chunk in enumerate(chunks):
            vec = embed_text(chunk)
            payload.append(
                (
                    idx,
                    chunk,
                    embedding_to_json(vec),
                    EMBEDDING_MODEL,
                    estimate_tokens(chunk),
                )
            )
        if payload:
            await self.documents.add_chunks(
                document_id=document_id,
                user_id=user_id,
                chat_id=chat_id,
                chunks=payload,
            )
        return len(payload)

    async def retrieve(
        self,
        *,
        user_id: int,
        chat_id: int,
        query: str,
        include_prior_chats: bool | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        include_prior = (
            self.settings.include_prior_chats_by_default
            if include_prior_chats is None
            else include_prior_chats
        )
        k = top_k or self.settings.retrieval_top_k
        query_vec = embed_text(query)

        chat_ids = [chat_id]
        if include_prior:
            recent = await self.chats.list_for_user(
                user_id,
                limit=self.settings.prior_chats_limit,
            )
            for chat in recent:
                if chat.id not in chat_ids:
                    chat_ids.append(chat.id)

        results: list[RetrievedChunk] = []

        message_chunks = await self.messages.list_chunks_for_user(
            user_id,
            chat_ids=chat_ids,
            limit=400,
        )
        for chunk in message_chunks:
            vec = embedding_from_json(chunk.embedding_json)
            score = cosine_similarity(query_vec, vec) if vec else 0.0
            results.append(
                RetrievedChunk(
                    source="message",
                    content=chunk.content,
                    score=score,
                    chat_id=chunk.chat_id,
                    message_id=chunk.message_id,
                )
            )

        doc_chunks = await self.documents.list_chunks_for_user(
            user_id,
            chat_ids=chat_ids,
            limit=400,
        )
        for chunk in doc_chunks:
            vec = embedding_from_json(chunk.embedding_json)
            score = cosine_similarity(query_vec, vec) if vec else 0.0
            results.append(
                RetrievedChunk(
                    source="document",
                    content=chunk.content,
                    score=score,
                    chat_id=chunk.chat_id,
                    document_id=chunk.document_id,
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return [item for item in results if item.score > 0.05][:k]

    def format_context(self, chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return ""
        lines = ["Relevant memory:"]
        for i, chunk in enumerate(chunks, start=1):
            label = chunk.source
            if chunk.document_id:
                label = f"document#{chunk.document_id}"
            elif chunk.message_id:
                label = f"message#{chunk.message_id}"
            lines.append(f"[{i}] ({label}, score={chunk.score:.2f}) {chunk.content}")
        return "\n".join(lines)

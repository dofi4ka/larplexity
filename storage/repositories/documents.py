from __future__ import annotations

from storage.db import Database
from storage.models import Document, DocumentChunk, utcnow_iso


class DocumentRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(
        self,
        *,
        user_id: int,
        chat_id: int | None,
        filename: str,
        mime_type: str | None,
        storage_path: str,
        byte_size: int,
        status: str = "pending",
    ) -> Document:
        now = utcnow_iso()
        cursor = await self.db.execute(
            """
            INSERT INTO documents(
                user_id, chat_id, filename, mime_type, storage_path, byte_size, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, chat_id, filename, mime_type, storage_path, byte_size, status, now),
        )
        doc = await self.get_by_id(int(cursor.lastrowid))
        assert doc is not None
        return doc

    async def get_by_id(self, document_id: int) -> Document | None:
        row = await self.db.fetchone("SELECT * FROM documents WHERE id = ?", (document_id,))
        return self._to_model(row) if row else None

    async def update_status(self, document_id: int, status: str) -> None:
        await self.db.execute(
            "UPDATE documents SET status = ? WHERE id = ?",
            (status, document_id),
        )

    async def add_chunks(
        self,
        *,
        document_id: int,
        user_id: int,
        chat_id: int | None,
        chunks: list[tuple[int, str, str | None, str | None, int | None]],
    ) -> None:
        now = utcnow_iso()
        params = [
            (
                document_id,
                user_id,
                chat_id,
                idx,
                content,
                embedding_json,
                embedding_model,
                token_count,
                now,
            )
            for idx, content, embedding_json, embedding_model, token_count in chunks
        ]
        await self.db.executemany(
            """
            INSERT INTO document_chunks(
                document_id, user_id, chat_id, chunk_index, content,
                embedding_json, embedding_model, token_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params,
        )

    async def list_chunks_for_user(
        self,
        user_id: int,
        *,
        chat_ids: list[int] | None = None,
        limit: int = 500,
    ) -> list[DocumentChunk]:
        if chat_ids:
            placeholders = ",".join("?" * len(chat_ids))
            rows = await self.db.fetchall(
                f"""
                SELECT * FROM document_chunks
                WHERE user_id = ? AND (chat_id IS NULL OR chat_id IN ({placeholders}))
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, *chat_ids, limit),
            )
        else:
            rows = await self.db.fetchall(
                """
                SELECT * FROM document_chunks
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
        return [self._chunk_model(row) for row in rows]

    @staticmethod
    def _to_model(row) -> Document:
        return Document(
            id=row["id"],
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            filename=row["filename"],
            mime_type=row["mime_type"],
            storage_path=row["storage_path"],
            byte_size=row["byte_size"],
            status=row["status"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _chunk_model(row) -> DocumentChunk:
        return DocumentChunk(
            id=row["id"],
            document_id=row["document_id"],
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            embedding_json=row["embedding_json"],
            embedding_model=row["embedding_model"],
            token_count=row["token_count"],
            created_at=row["created_at"],
        )

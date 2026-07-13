from __future__ import annotations

import json
from typing import Any

from storage.db import Database
from storage.models import Message, MessageChunk, utcnow_iso


class MessageRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(
        self,
        chat_id: int,
        role: str,
        content: str,
        *,
        telegram_message_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        now = utcnow_iso()
        cursor = await self.db.execute(
            """
            INSERT INTO messages(chat_id, role, content, telegram_message_id, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                role,
                content,
                telegram_message_id,
                json.dumps(metadata) if metadata else None,
                now,
            ),
        )
        message = await self.get_by_id(int(cursor.lastrowid))
        assert message is not None
        return message

    async def get_by_id(self, message_id: int) -> Message | None:
        row = await self.db.fetchone("SELECT * FROM messages WHERE id = ?", (message_id,))
        return self._to_model(row) if row else None

    async def list_recent(self, chat_id: int, limit: int = 40) -> list[Message]:
        rows = await self.db.fetchall(
            """
            SELECT * FROM (
                SELECT * FROM messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) sub
            ORDER BY id ASC
            """,
            (chat_id, limit),
        )
        return [self._to_model(row) for row in rows]

    async def count_for_chat(self, chat_id: int) -> int:
        row = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM messages WHERE chat_id = ?",
            (chat_id,),
        )
        return int(row["c"]) if row else 0

    async def add_chunks(
        self,
        *,
        message_id: int,
        chat_id: int,
        user_id: int,
        chunks: list[tuple[int, str, str | None, str | None, int | None]],
    ) -> None:
        now = utcnow_iso()
        params = [
            (
                message_id,
                chat_id,
                user_id,
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
            INSERT INTO message_chunks(
                message_id, chat_id, user_id, chunk_index, content,
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
    ) -> list[MessageChunk]:
        if chat_ids:
            placeholders = ",".join("?" * len(chat_ids))
            rows = await self.db.fetchall(
                f"""
                SELECT * FROM message_chunks
                WHERE user_id = ? AND chat_id IN ({placeholders})
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, *chat_ids, limit),
            )
        else:
            rows = await self.db.fetchall(
                """
                SELECT * FROM message_chunks
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
        return [self._chunk_model(row) for row in rows]

    @staticmethod
    def _to_model(row) -> Message:
        return Message(
            id=row["id"],
            chat_id=row["chat_id"],
            role=row["role"],
            content=row["content"],
            telegram_message_id=row["telegram_message_id"],
            metadata_json=row["metadata_json"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _chunk_model(row) -> MessageChunk:
        return MessageChunk(
            id=row["id"],
            message_id=row["message_id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            embedding_json=row["embedding_json"],
            embedding_model=row["embedding_model"],
            token_count=row["token_count"],
            created_at=row["created_at"],
        )

from __future__ import annotations

from storage.db import Database
from storage.models import Chat, utcnow_iso


class ChatRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(self, user_id: int, title: str = "New chat") -> Chat:
        now = utcnow_iso()
        cursor = await self.db.execute(
            """
            INSERT INTO chats(user_id, title, summary, is_archived, created_at, updated_at, last_message_at)
            VALUES (?, ?, NULL, 0, ?, ?, NULL)
            """,
            (user_id, title, now, now),
        )
        chat = await self.get_by_id(int(cursor.lastrowid))
        assert chat is not None
        await self.set_active(user_id, chat.id)
        return chat

    async def get_by_id(self, chat_id: int) -> Chat | None:
        row = await self.db.fetchone("SELECT * FROM chats WHERE id = ?", (chat_id,))
        return self._to_model(row) if row else None

    async def get_for_user(self, user_id: int, chat_id: int) -> Chat | None:
        row = await self.db.fetchone(
            "SELECT * FROM chats WHERE id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        return self._to_model(row) if row else None

    async def list_for_user(
        self,
        user_id: int,
        *,
        limit: int,
        offset: int = 0,
        include_archived: bool = False,
    ) -> list[Chat]:
        if include_archived:
            rows = await self.db.fetchall(
                """
                SELECT * FROM chats
                WHERE user_id = ?
                ORDER BY COALESCE(last_message_at, updated_at) DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            )
        else:
            rows = await self.db.fetchall(
                """
                SELECT * FROM chats
                WHERE user_id = ? AND is_archived = 0
                ORDER BY COALESCE(last_message_at, updated_at) DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            )
        return [self._to_model(row) for row in rows]

    async def count_for_user(self, user_id: int, *, include_archived: bool = False) -> int:
        if include_archived:
            row = await self.db.fetchone(
                "SELECT COUNT(*) AS c FROM chats WHERE user_id = ?",
                (user_id,),
            )
        else:
            row = await self.db.fetchone(
                "SELECT COUNT(*) AS c FROM chats WHERE user_id = ? AND is_archived = 0",
                (user_id,),
            )
        return int(row["c"]) if row else 0

    async def set_active(self, user_id: int, chat_id: int) -> None:
        now = utcnow_iso()
        await self.db.execute(
            """
            INSERT INTO user_active_chats(user_id, chat_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id, updated_at = excluded.updated_at
            """,
            (user_id, chat_id, now),
        )

    async def get_active(self, user_id: int) -> Chat | None:
        row = await self.db.fetchone(
            """
            SELECT c.*
            FROM user_active_chats uac
            JOIN chats c ON c.id = uac.chat_id
            WHERE uac.user_id = ?
            """,
            (user_id,),
        )
        return self._to_model(row) if row else None

    async def update_title(self, chat_id: int, title: str) -> None:
        await self.db.execute(
            "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
            (title[:80], utcnow_iso(), chat_id),
        )

    async def update_summary(self, chat_id: int, summary: str) -> None:
        await self.db.execute(
            "UPDATE chats SET summary = ?, updated_at = ? WHERE id = ?",
            (summary, utcnow_iso(), chat_id),
        )

    async def touch(self, chat_id: int) -> None:
        now = utcnow_iso()
        await self.db.execute(
            "UPDATE chats SET updated_at = ?, last_message_at = ? WHERE id = ?",
            (now, now, chat_id),
        )

    async def archive(self, chat_id: int) -> None:
        await self.db.execute(
            "UPDATE chats SET is_archived = 1, updated_at = ? WHERE id = ?",
            (utcnow_iso(), chat_id),
        )

    @staticmethod
    def _to_model(row) -> Chat:
        return Chat(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            summary=row["summary"],
            is_archived=bool(row["is_archived"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_message_at=row["last_message_at"],
        )

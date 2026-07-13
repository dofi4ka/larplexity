from __future__ import annotations

from storage.db import Database
from storage.models import User, utcnow_iso


class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def upsert(
        self,
        telegram_id: int,
        username: str | None,
        display_name: str | None,
    ) -> User:
        now = utcnow_iso()
        existing = await self.get_by_telegram_id(telegram_id)
        if existing:
            await self.db.execute(
                """
                UPDATE users
                SET username = ?, display_name = ?, updated_at = ?
                WHERE telegram_id = ?
                """,
                (username, display_name, now, telegram_id),
            )
            user = await self.get_by_telegram_id(telegram_id)
            assert user is not None
            return user

        cursor = await self.db.execute(
            """
            INSERT INTO users(telegram_id, username, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (telegram_id, username, display_name, now, now),
        )
        user = await self.get_by_id(int(cursor.lastrowid))
        assert user is not None
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        row = await self.db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._to_model(row) if row else None

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        row = await self.db.fetchone(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        return self._to_model(row) if row else None

    @staticmethod
    def _to_model(row) -> User:
        return User(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            display_name=row["display_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

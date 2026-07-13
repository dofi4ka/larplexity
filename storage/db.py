from __future__ import annotations

from pathlib import Path

import aiosqlite
import structlog

log = structlog.get_logger(__name__)

SCHEMA_VERSION = 1


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.execute("PRAGMA busy_timeout = 5000")
        await self.migrate()
        log.info("database_connected", path=str(self.path))

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            log.info("database_closed")

    async def migrate(self) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        await self._conn.commit()

        cursor = await self._conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        )
        row = await cursor.fetchone()
        current = int(row["version"]) if row else 0

        if current >= SCHEMA_VERSION:
            return

        schema_path = Path(__file__).with_name("schema.sql")
        sql = schema_path.read_text(encoding="utf-8")
        await self._conn.executescript(sql)
        await self._conn.execute(
            "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
            (SCHEMA_VERSION,),
        )
        await self._conn.commit()
        log.info("database_migrated", from_version=current, to_version=SCHEMA_VERSION)

    async def execute(self, sql: str, params: tuple | list = ()) -> aiosqlite.Cursor:
        cursor = await self.connection.execute(sql, params)
        await self.connection.commit()
        return cursor

    async def executemany(self, sql: str, params_seq: list[tuple]) -> None:
        await self.connection.executemany(sql, params_seq)
        await self.connection.commit()

    async def fetchone(self, sql: str, params: tuple | list = ()) -> aiosqlite.Row | None:
        cursor = await self.connection.execute(sql, params)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple | list = ()) -> list[aiosqlite.Row]:
        cursor = await self.connection.execute(sql, params)
        return await cursor.fetchall()

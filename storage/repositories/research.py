from __future__ import annotations

import json
from typing import Any

from storage.db import Database
from storage.models import Citation, ResearchRun, utcnow_iso


class ResearchRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(
        self,
        *,
        chat_id: int,
        user_id: int,
        query: str,
        status: str = "running",
    ) -> ResearchRun:
        now = utcnow_iso()
        cursor = await self.db.execute(
            """
            INSERT INTO research_runs(
                chat_id, user_id, query, status, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, user_id, query, status, now),
        )
        run = await self.get_by_id(int(cursor.lastrowid))
        assert run is not None
        return run

    async def get_by_id(self, run_id: int) -> ResearchRun | None:
        row = await self.db.fetchone("SELECT * FROM research_runs WHERE id = ?", (run_id,))
        return self._to_model(row) if row else None

    async def update(
        self,
        run_id: int,
        *,
        status: str | None = None,
        queries: list[str] | None = None,
        sources: list[dict[str, Any]] | None = None,
        facts: list[dict[str, Any]] | None = None,
        conflicts: list[dict[str, Any]] | None = None,
        answer: str | None = None,
        uncertainty_notes: str | None = None,
        completed: bool = False,
    ) -> None:
        run = await self.get_by_id(run_id)
        if run is None:
            return
        await self.db.execute(
            """
            UPDATE research_runs
            SET status = ?,
                queries_json = ?,
                sources_json = ?,
                facts_json = ?,
                conflicts_json = ?,
                answer = ?,
                uncertainty_notes = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                status or run.status,
                json.dumps(queries) if queries is not None else run.queries_json,
                json.dumps(sources) if sources is not None else run.sources_json,
                json.dumps(facts) if facts is not None else run.facts_json,
                json.dumps(conflicts) if conflicts is not None else run.conflicts_json,
                answer if answer is not None else run.answer,
                uncertainty_notes if uncertainty_notes is not None else run.uncertainty_notes,
                utcnow_iso() if completed else run.completed_at,
                run_id,
            ),
        )

    async def add_citation(
        self,
        *,
        chat_id: int,
        message_id: int | None,
        research_run_id: int | None,
        source_type: str,
        source_url: str | None,
        title: str | None,
        snippet: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> Citation:
        now = utcnow_iso()
        cursor = await self.db.execute(
            """
            INSERT INTO citations(
                chat_id, message_id, research_run_id, source_type, source_url,
                title, snippet, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                message_id,
                research_run_id,
                source_type,
                source_url,
                title,
                snippet,
                json.dumps(metadata) if metadata else None,
                now,
            ),
        )
        row = await self.db.fetchone("SELECT * FROM citations WHERE id = ?", (cursor.lastrowid,))
        assert row is not None
        return Citation(
            id=row["id"],
            chat_id=row["chat_id"],
            message_id=row["message_id"],
            research_run_id=row["research_run_id"],
            source_type=row["source_type"],
            source_url=row["source_url"],
            title=row["title"],
            snippet=row["snippet"],
            metadata_json=row["metadata_json"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _to_model(row) -> ResearchRun:
        return ResearchRun(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            query=row["query"],
            status=row["status"],
            queries_json=row["queries_json"],
            sources_json=row["sources_json"],
            facts_json=row["facts_json"],
            conflicts_json=row["conflicts_json"],
            answer=row["answer"],
            uncertainty_notes=row["uncertainty_notes"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

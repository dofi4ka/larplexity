from __future__ import annotations

from services.memory_service import MemoryService
from storage.models import RetrievedChunk


class HistoryTool:
    def __init__(self, memory: MemoryService) -> None:
        self.memory = memory

    async def search(
        self,
        *,
        user_id: int,
        chat_id: int,
        query: str,
        include_prior_chats: bool = True,
        top_k: int = 8,
    ) -> list[RetrievedChunk]:
        return await self.memory.retrieve(
            user_id=user_id,
            chat_id=chat_id,
            query=query,
            include_prior_chats=include_prior_chats,
            top_k=top_k,
        )

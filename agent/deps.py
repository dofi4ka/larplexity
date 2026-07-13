from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from config import Settings
from services.http_client import HttpClient
from services.memory_service import MemoryService
from storage.repositories.messages import MessageRepository
from storage.repositories.research import ResearchRepository
from tools.hackernews import HackerNewsTool
from tools.history import HistoryTool
from tools.web_search import TavilySearchTool
from tools.webpage import WebpageTool

StatusCallback = Callable[[str], Awaitable[None]]


@dataclass
class AgentDeps:
    settings: Settings
    http: HttpClient
    memory: MemoryService
    messages: MessageRepository
    research: ResearchRepository
    web_search: TavilySearchTool
    webpage: WebpageTool
    hackernews: HackerNewsTool
    history: HistoryTool
    user_id: int
    chat_id: int
    telegram_user_id: int
    status: StatusCallback | None = None
    citations: list[dict] = field(default_factory=list)

    async def notify(self, step: str) -> None:
        if self.status is not None:
            await self.status(step)

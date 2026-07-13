from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import Settings
from services.chat_service import ChatService
from services.http_client import HttpClient
from services.ingest_service import IngestService
from services.memory_service import MemoryService
from services.rate_limit import RateLimiter
from storage.db import Database
from storage.repositories.chats import ChatRepository
from storage.repositories.documents import DocumentRepository
from storage.repositories.messages import MessageRepository
from storage.repositories.research import ResearchRepository
from storage.repositories.users import UserRepository
from tools.hackernews import HackerNewsTool
from tools.history import HistoryTool
from tools.web_search import TavilySearchTool
from tools.webpage import WebpageTool


@dataclass
class AppContainer:
    settings: Settings
    db: Database
    http: HttpClient
    users: UserRepository
    chats: ChatRepository
    messages: MessageRepository
    documents: DocumentRepository
    research: ResearchRepository
    memory: MemoryService
    chat_service: ChatService
    ingest: IngestService
    web_search: TavilySearchTool
    webpage: WebpageTool
    hackernews: HackerNewsTool
    history: HistoryTool
    agent: Any
    rate_limiter: RateLimiter

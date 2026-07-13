from __future__ import annotations

import asyncio

import structlog
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from agent.agent import create_agent
from bot.container import AppContainer
from bot.handlers import setup_routers
from bot.middlewares.access import AccessMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware
from config import Settings, get_settings
from logging_config import setup_logging
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

log = structlog.get_logger(__name__)


async def build_container(settings: Settings) -> AppContainer:
    db = Database(settings.sqlite_path)
    await db.connect()

    http = HttpClient(
        timeout=settings.http_timeout_seconds,
        max_retries=settings.http_max_retries,
    )
    await http.start()

    users = UserRepository(db)
    chats = ChatRepository(db)
    messages = MessageRepository(db)
    documents = DocumentRepository(db)
    research = ResearchRepository(db)
    memory = MemoryService(settings, messages, documents, chats)
    chat_service = ChatService(settings, users, chats, messages, memory)
    ingest = IngestService(settings, documents, memory)
    web_search = TavilySearchTool(
        http,
        settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else None,
        max_results=settings.max_search_results,
    )
    webpage = WebpageTool(http, max_chars=settings.max_webpage_chars)
    hackernews = HackerNewsTool(http)
    history = HistoryTool(memory)
    agent = create_agent(settings)
    rate_limiter = RateLimiter(
        settings.rate_limit_requests,
        settings.rate_limit_window_seconds,
    )

    return AppContainer(
        settings=settings,
        db=db,
        http=http,
        users=users,
        chats=chats,
        messages=messages,
        documents=documents,
        research=research,
        memory=memory,
        chat_service=chat_service,
        ingest=ingest,
        web_search=web_search,
        webpage=webpage,
        hackernews=hackernews,
        history=history,
        agent=agent,
        rate_limiter=rate_limiter,
    )


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def create_health_app() -> Starlette:
    return Starlette(routes=[Route("/healthz", health)])


async def run_health_server(settings: Settings) -> uvicorn.Server:
    config = uvicorn.Config(
        create_health_app(),
        host=settings.health_host,
        port=settings.health_port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())
    return server


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log.info("starting_bot", model=settings.llm_model, base_url=settings.llm_base_url)

    container = await build_container(settings)
    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp["container"] = container

    # Dependency injection via middleware-like workflow values
    @dp.update.outer_middleware()
    async def inject_container(handler, event, data):
        data["container"] = container
        return await handler(event, data)

    dp.message.middleware(AccessMiddleware(settings))
    dp.callback_query.middleware(AccessMiddleware(settings))
    dp.message.middleware(RateLimitMiddleware(container.rate_limiter))
    dp.callback_query.middleware(RateLimitMiddleware(container.rate_limiter))

    dp.include_router(setup_routers())

    health_server = await run_health_server(settings)
    try:
        await dp.start_polling(bot)
    finally:
        health_server.should_exit = True
        await container.http.stop()
        await container.db.close()
        await bot.session.close()
        log.info("bot_stopped")


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()

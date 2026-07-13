from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration

from agent.agent import history_from_messages, persist_citations, run_agent
from agent.deps import AgentDeps
from bot.container import AppContainer
from bot.formatting import send_html
from services.status_updater import StatusUpdater

router = Router(name="messages")
log = structlog.get_logger(__name__)


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, container: AppContainer) -> None:
    assert message.from_user
    assert message.text

    user = await container.chat_service.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    chat = await container.chat_service.get_or_create_active_chat(user)
    await container.chat_service.add_user_message(
        user=user,
        chat=chat,
        content=message.text,
        telegram_message_id=message.message_id,
    )

    status_msg = await message.answer(
        html_decoration.bold("Working"),
        parse_mode=ParseMode.HTML,
    )
    updater = StatusUpdater(
        message.bot,
        message.chat.id,
        status_msg.message_id,
        title="Working",
    )

    deps = AgentDeps(
        settings=container.settings,
        http=container.http,
        memory=container.memory,
        messages=container.messages,
        research=container.research,
        web_search=container.web_search,
        webpage=container.webpage,
        hackernews=container.hackernews,
        history=container.history,
        user_id=user.id,
        chat_id=chat.id,
        telegram_user_id=message.from_user.id,
        status=updater.add_step,
    )

    recent = await container.messages.list_recent(chat.id, limit=24)
    history = history_from_messages(recent[:-1])  # exclude just-added user message duplicate

    try:
        answer = await run_agent(
            container.agent,
            deps,
            message.text,
            message_history=history,
        )
        await updater.finish(html_decoration.bold("Done"))
        sent = await send_html(message, answer)
        saved = await container.chat_service.add_assistant_message(
            user=user,
            chat=chat,
            content=answer,
            telegram_message_id=sent.message_id,
        )
        if deps.citations:
            await persist_citations(
                container.research,
                chat_id=chat.id,
                message_id=saved.id,
                citations=deps.citations,
            )
    except Exception as exc:
        log.exception("agent_failed", error=str(exc))
        await updater.finish(html_decoration.quote(f"Error: {exc}"))

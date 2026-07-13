from __future__ import annotations

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration

from agent.deps import AgentDeps
from agent.research import DeepResearchPipeline
from bot.container import AppContainer
from bot.formatting import format_help, send_html
from bot.keyboards.chats import chats_keyboard
from services.status_updater import StatusUpdater

router = Router(name="commands")


def _deps_from_message(container: AppContainer, user_id: int, chat_id: int, telegram_user_id: int) -> AgentDeps:
    return AgentDeps(
        settings=container.settings,
        http=container.http,
        memory=container.memory,
        messages=container.messages,
        research=container.research,
        web_search=container.web_search,
        webpage=container.webpage,
        hackernews=container.hackernews,
        history=container.history,
        user_id=user_id,
        chat_id=chat_id,
        telegram_user_id=telegram_user_id,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, container: AppContainer) -> None:
    assert message.from_user
    user = await container.chat_service.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    chat = await container.chat_service.get_or_create_active_chat(user)
    await message.answer(
        format_help()
        + f"\n\nActive chat: {html_decoration.bold(html_decoration.quote(chat.title))} (#{chat.id})",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(format_help(), parse_mode=ParseMode.HTML)


@router.message(Command("new"))
async def cmd_new(message: Message, container: AppContainer) -> None:
    assert message.from_user
    user = await container.chat_service.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    chat = await container.chat_service.new_chat(user)
    await message.answer(
        f"Started {html_decoration.bold('new chat')} #{chat.id}.\n"
        "Telegram history is unchanged.",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, container: AppContainer) -> None:
    assert message.from_user
    user = await container.chat_service.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    chat = await container.chat_service.reset_chat(user)
    await message.answer(
        f"Chat reset. Previous session archived in bot memory.\n"
        f"Active chat: #{chat.id}\n"
        "Telegram message history was not modified.",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("chats"))
async def cmd_chats(message: Message, container: AppContainer) -> None:
    assert message.from_user
    user = await container.chat_service.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    page = 0
    chats, total = await container.chat_service.list_chats(user, page=page)
    if not chats:
        await message.answer("No chats yet. Send a message or /new.")
        return
    active = await container.chats.get_active(user.id)
    active_line = f"Active: #{active.id} · {active.title}" if active else "No active chat"
    await message.answer(
        f"{html_decoration.bold('Your chats')}\n{html_decoration.quote(active_line)}\n"
        f"Page 1 · {total} total",
        parse_mode=ParseMode.HTML,
        reply_markup=chats_keyboard(
            chats,
            page=page,
            total=total,
            page_size=container.settings.chats_page_size,
        ),
    )


@router.message(Command("research"))
async def cmd_research(message: Message, command: CommandObject, container: AppContainer) -> None:
    assert message.from_user
    topic = (command.args or "").strip()
    if not topic:
        await message.answer("Usage: /research &lt;topic&gt;", parse_mode=ParseMode.HTML)
        return

    user = await container.chat_service.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    chat = await container.chat_service.get_or_create_active_chat(user)
    await container.chat_service.add_user_message(
        user=user,
        chat=chat,
        content=f"/research {topic}",
        telegram_message_id=message.message_id,
    )

    status_msg = await message.answer(
        html_decoration.bold("Deep research"),
        parse_mode=ParseMode.HTML,
    )
    updater = StatusUpdater(
        message.bot,
        message.chat.id,
        status_msg.message_id,
        title="Deep research",
    )

    deps = _deps_from_message(container, user.id, chat.id, message.from_user.id)
    deps.status = updater.add_step

    try:
        pipeline = DeepResearchPipeline(container.settings)
        result = await pipeline.run(deps, topic)
        answer = result["answer"]
        if result.get("uncertainty_notes"):
            notes = result["uncertainty_notes"]
            if isinstance(notes, list):
                notes_text = "\n".join(f"- {n}" for n in notes)
            else:
                notes_text = str(notes)
            if "Uncertainty" not in answer:
                answer = f"{answer}\n\nUncertainty:\n{notes_text}"
        await updater.finish(html_decoration.bold("Deep research complete"))
        sent = await send_html(message, answer)
        await container.chat_service.add_assistant_message(
            user=user,
            chat=chat,
            content=answer,
            telegram_message_id=sent.message_id,
            metadata={"research_run_id": result.get("research_run_id")},
        )
    except Exception as exc:
        await updater.finish(html_decoration.quote(f"Deep research failed: {exc}"))

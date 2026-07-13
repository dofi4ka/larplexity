from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery
from aiogram.utils.text_decorations import html_decoration

from bot.container import AppContainer
from bot.formatting import send_html
from bot.keyboards.chats import chats_keyboard
from services.status_updater import StatusUpdater

router = Router(name="callbacks")


@router.callback_query(F.data.startswith("chat:page:"))
async def on_chats_page(callback: CallbackQuery, container: AppContainer) -> None:
    assert callback.from_user
    assert callback.data
    assert callback.message
    page = int(callback.data.split(":")[-1])
    user = await container.chat_service.ensure_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name,
    )
    chats, total = await container.chat_service.list_chats(user, page=page)
    active = await container.chats.get_active(user.id)
    active_line = f"Active: #{active.id} · {active.title}" if active else "No active chat"
    await callback.message.edit_text(
        f"{html_decoration.bold('Your chats')}\n{html_decoration.quote(active_line)}\n"
        f"Page {page + 1} · {total} total",
        parse_mode=ParseMode.HTML,
        reply_markup=chats_keyboard(
            chats,
            page=page,
            total=total,
            page_size=container.settings.chats_page_size,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chat:restore:"))
async def on_chat_restore(callback: CallbackQuery, container: AppContainer) -> None:
    assert callback.from_user
    assert callback.data
    assert callback.message
    chat_id = int(callback.data.split(":")[-1])
    user = await container.chat_service.ensure_user(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name,
    )
    chat = await container.chat_service.restore_chat(user, chat_id)
    if chat is None:
        await callback.answer("Chat not found", show_alert=True)
        return

    await callback.answer(f"Restored chat #{chat.id}")
    # Do not touch Telegram history — only bot-side active chat switches.
    status = await callback.message.answer(
        html_decoration.bold(f"Restored: {html_decoration.quote(chat.title)}"),
        parse_mode=ParseMode.HTML,
    )
    updater = StatusUpdater(
        callback.bot,
        callback.message.chat.id,
        status.message_id,
        title="Generating session recap",
    )
    await updater.add_step("Loading chat memory")
    recap = await container.chat_service.build_recap(chat)
    await updater.finish(html_decoration.bold("Session restored"))
    await send_html(
        callback.message,
        f"Restored chat #{chat.id}: {chat.title}\n\n{recap}",
    )

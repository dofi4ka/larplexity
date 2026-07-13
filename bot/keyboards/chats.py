from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from storage.models import Chat


def chats_keyboard(chats: list[Chat], page: int, total: int, page_size: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for chat in chats:
        title = chat.title or f"Chat #{chat.id}"
        builder.row(
            InlineKeyboardButton(
                text=f"#{chat.id} · {title[:40]}",
                callback_data=f"chat:restore:{chat.id}",
            )
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="« Prev", callback_data=f"chat:page:{page - 1}")
        )
    max_page = max(0, (total - 1) // page_size) if total else 0
    if page < max_page:
        nav.append(
            InlineKeyboardButton(text="Next »", callback_data=f"chat:page:{page + 1}")
        )
    if nav:
        builder.row(*nav)
    return builder.as_markup()

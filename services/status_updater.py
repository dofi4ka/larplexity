from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.text_decorations import html_decoration

import structlog

log = structlog.get_logger(__name__)


class StatusUpdater:
    """Edits a single Telegram status message as tools run."""

    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        *,
        title: str = "Working",
    ) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.title = title
        self.steps: list[str] = []
        self._last_text = ""

    async def set_title(self, title: str) -> None:
        self.title = title
        await self._render()

    async def add_step(self, step: str) -> None:
        cleaned = step.strip()
        if not cleaned:
            return
        if self.steps and self.steps[-1] == cleaned:
            return
        self.steps.append(cleaned)
        # Keep Telegram message reasonably short
        if len(self.steps) > 12:
            self.steps = self.steps[-12:]
        await self._render()

    async def finish(self, text: str) -> None:
        await self._edit(text)

    async def _render(self) -> None:
        lines = [html_decoration.bold(self.title)]
        for step in self.steps:
            lines.append(f"• {html_decoration.quote(step)}")
        await self._edit("\n".join(lines))

    async def _edit(self, text: str) -> None:
        if text == self._last_text:
            return
        try:
            await self.bot.edit_message_text(
                text=text,
                chat_id=self.chat_id,
                message_id=self.message_id,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            self._last_text = text
        except TelegramBadRequest as exc:
            # Ignore "message is not modified" and rare race conditions.
            if "message is not modified" in str(exc).lower():
                return
            log.warning("status_edit_failed", error=str(exc))

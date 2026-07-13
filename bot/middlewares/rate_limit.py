from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from services.rate_limit import RateLimiter


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, limiter: RateLimiter) -> None:
        self.limiter = limiter

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        if user is None:
            return await handler(event, data)

        allowed = await self.limiter.allow(user.id)
        if not allowed:
            if isinstance(event, Message):
                await event.answer("Rate limit exceeded. Please wait a bit.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Rate limit exceeded.", show_alert=True)
            return None
        return await handler(event, data)

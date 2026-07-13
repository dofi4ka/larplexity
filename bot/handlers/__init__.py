from __future__ import annotations

from aiogram import Router

from bot.handlers import callbacks, commands, documents, messages


def setup_routers() -> Router:
    root = Router(name="root")
    root.include_router(commands.router)
    root.include_router(callbacks.router)
    root.include_router(documents.router)
    root.include_router(messages.router)
    return root

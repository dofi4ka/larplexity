from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import structlog
from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration

from bot.container import AppContainer
from services.status_updater import StatusUpdater

router = Router(name="documents")
log = structlog.get_logger(__name__)


@router.message(F.document)
async def on_document(message: Message, container: AppContainer) -> None:
    assert message.from_user
    assert message.document

    user = await container.chat_service.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
    )
    chat = await container.chat_service.get_or_create_active_chat(user)

    filename = message.document.file_name or f"file-{uuid4().hex}"
    ok, reason = container.ingest.is_allowed(filename, message.document.file_size)
    if not ok:
        await message.answer(html_decoration.quote(reason), parse_mode=ParseMode.HTML)
        return

    status_msg = await message.answer(
        html_decoration.bold("Ingesting file"),
        parse_mode=ParseMode.HTML,
    )
    updater = StatusUpdater(
        message.bot,
        message.chat.id,
        status_msg.message_id,
        title="Ingesting file",
    )

    suffix = Path(filename).suffix.lower()
    safe_name = f"{user.id}_{chat.id}_{uuid4().hex}{suffix}"
    target = (container.settings.uploads_dir / safe_name).resolve()
    uploads_root = container.settings.uploads_dir.resolve()
    if uploads_root not in target.parents and target.parent != uploads_root:
        await updater.finish("Refusing unsafe path")
        return

    try:
        await updater.add_step(f"Downloading {filename}")
        await message.bot.download(message.document, destination=target)
        await updater.add_step("Extracting & indexing")
        doc_id, chunks = await container.ingest.ingest_telegram_document(
            user_id=user.id,
            chat_id=chat.id,
            tg_document=message.document,
            local_path=target,
        )
        note = f"Ingested `{filename}` as document #{doc_id} ({chunks} chunks)."
        await container.chat_service.add_user_message(
            user=user,
            chat=chat,
            content=f"[uploaded file] {filename}",
            telegram_message_id=message.message_id,
        )
        await updater.finish(html_decoration.bold("File ready for RAG"))
        await message.answer(
            html_decoration.quote(note),
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        log.exception("ingest_failed", error=str(exc))
        if target.exists():
            try:
                target.unlink()
            except OSError:
                pass
        await updater.finish(html_decoration.quote(f"Ingest failed: {exc}"))

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from config import Settings
from services.embeddings import chunk_text, cosine_similarity, embed_text
from services.memory_service import MemoryService
from storage.db import Database
from storage.repositories.chats import ChatRepository
from storage.repositories.documents import DocumentRepository
from storage.repositories.messages import MessageRepository
from storage.repositories.users import UserRepository
from bot.formatting import to_html


def test_chunk_and_embed() -> None:
    chunks = chunk_text("hello world " * 100, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    a = embed_text("python telegram bot")
    b = embed_text("python telegram assistant")
    c = embed_text("gardening tomatoes soil")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)


def test_to_html_escapes_and_formats() -> None:
    html = to_html('Hello **world** and `code` with <script> & [link](https://example.com)')
    assert "<b>world</b>" in html
    assert "<code>code</code>" in html
    assert "&lt;script&gt;" in html
    assert 'href="https://example.com"' in html


@pytest.mark.asyncio
async def test_memory_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    settings = Settings(
        telegram_bot_token="x",
        llm_api_key="y",
        sqlite_path=db_path,
        uploads_dir=tmp_path / "uploads",
    )
    db = Database(db_path)
    await db.connect()
    users = UserRepository(db)
    chats = ChatRepository(db)
    messages = MessageRepository(db)
    documents = DocumentRepository(db)
    memory = MemoryService(settings, messages, documents, chats)

    user = await users.upsert(1, "tester", "Tester")
    chat = await chats.create(user.id, title="Test")
    msg = await messages.add(chat.id, "user", "I like Brazilian jiu-jitsu and espresso")
    await memory.index_message(
        user_id=user.id,
        chat_id=chat.id,
        message_id=msg.id,
        content=msg.content,
    )
    hits = await memory.retrieve(
        user_id=user.id,
        chat_id=chat.id,
        query="jiu-jitsu preferences",
        include_prior_chats=False,
    )
    assert hits
    assert "jiu-jitsu" in hits[0].content.lower()
    await db.close()

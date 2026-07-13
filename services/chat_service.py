from __future__ import annotations

import re

from config import Settings
from services.memory_service import MemoryService
from storage.models import Chat, Message, User
from storage.repositories.chats import ChatRepository
from storage.repositories.messages import MessageRepository
from storage.repositories.users import UserRepository


class ChatService:
    def __init__(
        self,
        settings: Settings,
        users: UserRepository,
        chats: ChatRepository,
        messages: MessageRepository,
        memory: MemoryService,
    ) -> None:
        self.settings = settings
        self.users = users
        self.chats = chats
        self.messages = messages
        self.memory = memory

    async def ensure_user(
        self,
        telegram_id: int,
        username: str | None,
        full_name: str | None,
    ) -> User:
        return await self.users.upsert(telegram_id, username, full_name)

    async def get_or_create_active_chat(self, user: User) -> Chat:
        active = await self.chats.get_active(user.id)
        if active and not active.is_archived:
            return active
        return await self.chats.create(user.id, title="New chat")

    async def new_chat(self, user: User) -> Chat:
        return await self.chats.create(user.id, title="New chat")

    async def reset_chat(self, user: User) -> Chat:
        """Archive current chat and start a fresh one. Telegram history untouched."""
        active = await self.chats.get_active(user.id)
        if active:
            await self.chats.archive(active.id)
        return await self.chats.create(user.id, title="New chat")

    async def restore_chat(self, user: User, chat_id: int) -> Chat | None:
        chat = await self.chats.get_for_user(user.id, chat_id)
        if chat is None:
            return None
        await self.chats.set_active(user.id, chat.id)
        return chat

    async def list_chats(self, user: User, page: int = 0) -> tuple[list[Chat], int]:
        page_size = self.settings.chats_page_size
        offset = max(0, page) * page_size
        total = await self.chats.count_for_user(user.id)
        items = await self.chats.list_for_user(user.id, limit=page_size, offset=offset)
        return items, total

    async def add_user_message(
        self,
        *,
        user: User,
        chat: Chat,
        content: str,
        telegram_message_id: int | None = None,
    ) -> Message:
        message = await self.messages.add(
            chat.id,
            "user",
            content,
            telegram_message_id=telegram_message_id,
        )
        await self.chats.touch(chat.id)
        await self.memory.index_message(
            user_id=user.id,
            chat_id=chat.id,
            message_id=message.id,
            content=content,
        )
        if chat.title == "New chat":
            await self.chats.update_title(chat.id, self._autotitle(content))
        await self.maybe_refresh_summary(user, chat)
        return message

    async def add_assistant_message(
        self,
        *,
        user: User,
        chat: Chat,
        content: str,
        telegram_message_id: int | None = None,
        metadata: dict | None = None,
    ) -> Message:
        message = await self.messages.add(
            chat.id,
            "assistant",
            content,
            telegram_message_id=telegram_message_id,
            metadata=metadata,
        )
        await self.chats.touch(chat.id)
        await self.memory.index_message(
            user_id=user.id,
            chat_id=chat.id,
            message_id=message.id,
            content=content,
        )
        await self.maybe_refresh_summary(user, chat)
        return message

    async def maybe_refresh_summary(self, user: User, chat: Chat) -> None:
        count = await self.messages.count_for_chat(chat.id)
        if count == 0 or count % self.settings.summarize_every_n_messages != 0:
            return
        recent = await self.messages.list_recent(chat.id, limit=30)
        summary = self._local_summary(recent)
        await self.chats.update_summary(chat.id, summary)

    async def build_recap(self, chat: Chat) -> str:
        if chat.summary:
            return chat.summary
        recent = await self.messages.list_recent(chat.id, limit=20)
        if not recent:
            return "This chat has no messages yet."
        return self._local_summary(recent)

    @staticmethod
    def _autotitle(content: str) -> str:
        cleaned = re.sub(r"\s+", " ", content).strip()
        if not cleaned:
            return "New chat"
        return (cleaned[:60] + "…") if len(cleaned) > 60 else cleaned

    @staticmethod
    def _local_summary(messages: list[Message]) -> str:
        user_bits = [m.content for m in messages if m.role == "user"][-5:]
        assistant_bits = [m.content for m in messages if m.role == "assistant"][-3:]
        parts = ["Session recap:"]
        if user_bits:
            parts.append("You discussed: " + " | ".join(
                re.sub(r"\s+", " ", bit)[:120] for bit in user_bits
            ))
        if assistant_bits:
            last = re.sub(r"\s+", " ", assistant_bits[-1])[:240]
            parts.append(f"Latest assistant takeaway: {last}")
        return "\n".join(parts)

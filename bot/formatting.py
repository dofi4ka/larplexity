from __future__ import annotations

import re

from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def to_html(text: str) -> str:
    """Convert a small safe markdown-ish subset into Telegram HTML entities."""
    return _apply_simple_inline(text)


def _apply_simple_inline(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "[":
            link = _MD_LINK_RE.match(text, i)
            if link:
                label = html_decoration.quote(link.group(1))
                url = html_decoration.quote(link.group(2))
                out.append(f'<a href="{url}">{label}</a>')
                i = link.end()
                continue
        if text.startswith("**", i):
            end = text.find("**", i + 2)
            if end != -1:
                out.append(html_decoration.bold(text[i + 2 : end]))
                i = end + 2
                continue
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end != -1 and end > i + 1:
                out.append(html_decoration.code(text[i + 1 : end]))
                i = end + 1
                continue
        out.append(html_decoration.quote(text[i]))
        i += 1
    html = "".join(out)
    return re.sub(r"\n{3,}", "\n\n", html).strip()


async def send_html(message: Message, text: str) -> Message:
    chunks = split_message(text, limit=3900)
    sent = None
    for chunk in chunks:
        sent = await message.answer(
            to_html(chunk),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    assert sent is not None
    return sent


def split_message(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    return chunks


def format_help() -> str:
    return (
        f"{html_decoration.bold('Larplexity')}\n"
        "Personal research assistant.\n\n"
        f"{html_decoration.bold('Commands')}\n"
        "/new — start a new conversation\n"
        "/reset — archive current chat and start fresh\n"
        "/chats — list conversations (restore with buttons)\n"
        "/research &lt;topic&gt; — deep multi-source research\n"
        "/help — show this help\n\n"
        "Send text to chat, or upload .txt/.md/.csv/.json/.pdf for RAG."
    )

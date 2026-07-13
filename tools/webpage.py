from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from services.http_client import HttpClient

_BLOCKED_SCHEMES = {"file", "ftp", "javascript", "data"}
_PRIVATE_HOST_MARKERS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "169.254.",
    "10.",
    "192.168.",
)


class WebpageTool:
    def __init__(self, http: HttpClient, max_chars: int = 20_000) -> None:
        self.http = http
        self.max_chars = max_chars

    def _validate_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("Only http/https URLs are allowed")
        if parsed.scheme.lower() in _BLOCKED_SCHEMES:
            raise ValueError("Blocked URL scheme")
        host = (parsed.hostname or "").lower()
        if not host:
            raise ValueError("Invalid URL host")
        if any(host.startswith(marker) or host == marker.rstrip(".") for marker in _PRIVATE_HOST_MARKERS):
            raise ValueError("Private/local network URLs are blocked")
        return url

    async def fetch(self, url: str) -> dict[str, Any]:
        safe_url = self._validate_url(url)
        response = await self.http.request("GET", safe_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type and "json" not in content_type:
            raise ValueError(f"Unsupported content type: {content_type}")

        text = response.text
        if "html" in content_type or "<html" in text[:200].lower():
            soup = BeautifulSoup(text, "lxml")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            title = (soup.title.string or "").strip() if soup.title else ""
            body = soup.get_text(separator=" ", strip=True)
        else:
            title = safe_url
            body = text

        body = re.sub(r"\s+", " ", body).strip()
        truncated = body[: self.max_chars]
        return {
            "url": safe_url,
            "title": title or safe_url,
            "content": truncated,
            "truncated": len(body) > self.max_chars,
            "chars": len(truncated),
        }

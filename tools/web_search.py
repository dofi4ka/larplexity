from __future__ import annotations

from typing import Any

from services.http_client import HttpClient


class TavilySearchTool:
    def __init__(
        self,
        http: HttpClient,
        api_key: str | None,
        *,
        max_results: int = 8,
    ) -> None:
        self.http = http
        self.api_key = api_key
        self.max_results = max_results

    async def search(self, query: str, max_results: int | None = None) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("TAVILY_API_KEY is not configured")
        limit = max_results or self.max_results
        response = await self.http.request(
            "POST",
            "https://api.tavily.com/search",
            json={
                "api_key": self.api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": False,
                "max_results": limit,
            },
        )
        response.raise_for_status()
        payload = response.json()
        results = []
        for item in payload.get("results", [])[:limit]:
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content"),
                    "score": item.get("score"),
                }
            )
        return results

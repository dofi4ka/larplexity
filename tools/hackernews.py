from __future__ import annotations

from typing import Any

from services.http_client import HttpClient

HN_API = "https://hacker-news.firebaseio.com/v0"


class HackerNewsTool:
    def __init__(self, http: HttpClient) -> None:
        self.http = http

    async def get_item(self, item_id: int) -> dict[str, Any]:
        response = await self.http.request("GET", f"{HN_API}/item/{item_id}.json")
        response.raise_for_status()
        data = response.json()
        if not data:
            raise ValueError(f"HN item {item_id} not found")
        return data

    async def top_stories(self, limit: int = 10) -> list[dict[str, Any]]:
        response = await self.http.request("GET", f"{HN_API}/topstories.json")
        response.raise_for_status()
        ids = response.json()[: max(1, min(limit, 30))]
        stories: list[dict[str, Any]] = []
        for item_id in ids:
            item = await self.get_item(int(item_id))
            if item.get("type") == "story":
                stories.append(self._summarize_story(item))
        return stories

    async def story_with_comments(self, item_id: int, max_comments: int = 20) -> dict[str, Any]:
        story = await self.get_item(item_id)
        if story.get("type") not in {"story", "ask", "job", "poll"}:
            raise ValueError("Item is not a story-like HN object")
        kids = story.get("kids") or []
        comments: list[dict[str, Any]] = []
        for kid_id in kids[: max(1, min(max_comments, 50))]:
            try:
                comment = await self.get_item(int(kid_id))
            except Exception:
                continue
            if comment.get("type") != "comment" or comment.get("deleted") or comment.get("dead"):
                continue
            comments.append(
                {
                    "id": comment.get("id"),
                    "by": comment.get("by"),
                    "text": comment.get("text"),
                    "time": comment.get("time"),
                }
            )
        result = self._summarize_story(story)
        result["comments"] = comments
        return result

    @staticmethod
    def _summarize_story(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "title": item.get("title"),
            "url": item.get("url"),
            "by": item.get("by"),
            "score": item.get("score"),
            "descendants": item.get("descendants"),
            "text": item.get("text"),
            "time": item.get("time"),
            "hn_url": f"https://news.ycombinator.com/item?id={item.get('id')}",
        }

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from openai import AsyncOpenAI

from agent.deps import AgentDeps
from agent.prompts import (
    RESEARCH_ANSWER_PROMPT,
    RESEARCH_FACTS_PROMPT,
    RESEARCH_QUERY_PROMPT,
)
from config import Settings


def _dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for source in sources:
        url = (source.get("url") or "").strip()
        key = url.lower() if url else (source.get("title") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(source)
    return unique


def _normalize_host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


class DeepResearchPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    async def run(self, deps: AgentDeps, topic: str) -> dict[str, Any]:
        run = await deps.research.create(
            chat_id=deps.chat_id,
            user_id=deps.user_id,
            query=topic,
            status="running",
        )
        try:
            await deps.notify("Deep research: generating search queries")
            queries = await self._generate_queries(topic)
            await deps.research.update(run.id, queries=queries, status="searching")

            sources: list[dict[str, Any]] = []
            for query in queries:
                await deps.notify(f"Searching: {query}")
                try:
                    hits = await deps.web_search.search(query, max_results=4)
                except Exception as exc:
                    await deps.notify(f"Search failed for '{query}': {exc}")
                    continue
                for hit in hits:
                    sources.append(
                        {
                            "title": hit.get("title"),
                            "url": hit.get("url"),
                            "snippet": hit.get("content"),
                            "query": query,
                        }
                    )

            sources = _dedupe_sources(sources)[: self.settings.research_max_sources]
            await deps.research.update(run.id, sources=sources, status="fetching")

            enriched: list[dict[str, Any]] = []
            for i, source in enumerate(sources, start=1):
                url = source.get("url")
                if not url:
                    continue
                await deps.notify(f"Fetching source [{i}]: {_normalize_host(url) or url}")
                try:
                    page = await deps.webpage.fetch(url)
                    enriched.append(
                        {
                            "index": i,
                            "title": page.get("title") or source.get("title"),
                            "url": url,
                            "snippet": source.get("snippet"),
                            "content": (page.get("content") or "")[:4000],
                        }
                    )
                except Exception:
                    enriched.append(
                        {
                            "index": i,
                            "title": source.get("title"),
                            "url": url,
                            "snippet": source.get("snippet"),
                            "content": source.get("snippet") or "",
                        }
                    )

            await deps.notify("Extracting facts and comparing claims")
            analysis = await self._extract_facts(topic, enriched)
            await deps.research.update(
                run.id,
                facts=analysis.get("facts"),
                conflicts=analysis.get("conflicts"),
                uncertainty_notes="\n".join(analysis.get("uncertainty_notes") or []),
                status="answering",
            )

            await deps.notify("Writing researched answer")
            answer = await self._compose_answer(topic, enriched, analysis)

            for item in enriched:
                deps.citations.append(
                    {
                        "source_type": "web",
                        "source_url": item.get("url"),
                        "title": item.get("title"),
                        "snippet": item.get("snippet"),
                    }
                )
                await deps.research.add_citation(
                    chat_id=deps.chat_id,
                    message_id=None,
                    research_run_id=run.id,
                    source_type="web",
                    source_url=item.get("url"),
                    title=item.get("title"),
                    snippet=item.get("snippet"),
                )

            uncertainty = "\n".join(analysis.get("uncertainty_notes") or [])
            await deps.research.update(
                run.id,
                status="completed",
                answer=answer,
                uncertainty_notes=uncertainty,
                completed=True,
            )
            return {
                "answer": answer,
                "queries": queries,
                "sources": enriched,
                "facts": analysis.get("facts", []),
                "conflicts": analysis.get("conflicts", []),
                "uncertainty_notes": analysis.get("uncertainty_notes", []),
                "research_run_id": run.id,
            }
        except Exception as exc:
            await deps.research.update(run.id, status="failed", completed=True)
            raise RuntimeError(f"Deep research failed: {exc}") from exc

    async def _generate_queries(self, topic: str) -> list[str]:
        n = self.settings.research_max_queries
        content = await self._chat(
            RESEARCH_QUERY_PROMPT.format(n=n, topic=topic),
            temperature=0.4,
        )
        queries = self._parse_json_list(content)
        cleaned = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
        if topic not in cleaned:
            cleaned.insert(0, topic)
        return cleaned[:n]

    async def _extract_facts(self, topic: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
        compact = []
        for src in sources:
            compact.append(
                {
                    "index": src.get("index"),
                    "title": src.get("title"),
                    "url": src.get("url"),
                    "content": (src.get("content") or src.get("snippet") or "")[:2500],
                }
            )
        content = await self._chat(
            RESEARCH_FACTS_PROMPT.format(
                topic=topic,
                sources=json.dumps(compact, ensure_ascii=False),
            ),
            temperature=0.2,
        )
        data = self._parse_json_obj(content)
        return {
            "facts": data.get("facts") or [],
            "conflicts": data.get("conflicts") or [],
            "uncertainty_notes": data.get("uncertainty_notes") or [],
        }

    async def _compose_answer(
        self,
        topic: str,
        sources: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> str:
        source_lines = [
            f"[{s.get('index')}] {s.get('title')} — {s.get('url')}" for s in sources
        ]
        content = await self._chat(
            RESEARCH_ANSWER_PROMPT.format(
                topic=topic,
                facts=json.dumps(analysis, ensure_ascii=False),
                sources="\n".join(source_lines),
            ),
            temperature=0.3,
        )
        return content.strip()

    async def _chat(self, prompt: str, temperature: float = 0.3) -> str:
        response = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a careful research assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _parse_json_list(text: str) -> list[Any]:
        match = re.search(r"\[.*\]", text, flags=re.DOTALL)
        raw = match.group(0) if match else text
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return [line.strip("- •\t ") for line in text.splitlines() if line.strip()]
        return data if isinstance(data, list) else []

    @staticmethod
    def _parse_json_obj(text: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        raw = match.group(0) if match else text
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "facts": [],
                "conflicts": [],
                "uncertainty_notes": ["Model returned non-JSON fact extraction."],
            }
        return data if isinstance(data, dict) else {}

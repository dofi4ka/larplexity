from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from agent.deps import AgentDeps
from agent.prompts import SYSTEM_PROMPT
from agent.research import DeepResearchPipeline
from config import Settings


def build_model(settings: Settings) -> OpenAIChatModel:
    provider = OpenAIProvider(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
    )
    return OpenAIChatModel(settings.llm_model, provider=provider)


def create_agent(settings: Settings) -> Agent[AgentDeps, str]:
    agent: Agent[AgentDeps, str] = Agent(
        build_model(settings),
        deps_type=AgentDeps,
        system_prompt=SYSTEM_PROMPT,
        retries=settings.llm_max_retries,
    )

    @agent.tool
    async def web_search(ctx: RunContext[AgentDeps], query: str, max_results: int = 5) -> str:
        """Search the web with Tavily for up-to-date information."""
        await ctx.deps.notify(f"Web search: {query}")
        results = await ctx.deps.web_search.search(query, max_results=max_results)
        for item in results:
            ctx.deps.citations.append(
                {
                    "source_type": "web",
                    "source_url": item.get("url"),
                    "title": item.get("title"),
                    "snippet": item.get("content"),
                }
            )
        return json.dumps(results, ensure_ascii=False)

    @agent.tool
    async def fetch_webpage(ctx: RunContext[AgentDeps], url: str) -> str:
        """Fetch and extract readable text from a public webpage."""
        await ctx.deps.notify(f"Fetching page: {url}")
        page = await ctx.deps.webpage.fetch(url)
        ctx.deps.citations.append(
            {
                "source_type": "webpage",
                "source_url": page.get("url"),
                "title": page.get("title"),
                "snippet": (page.get("content") or "")[:400],
            }
        )
        return json.dumps(page, ensure_ascii=False)

    @agent.tool
    async def hn_top_stories(ctx: RunContext[AgentDeps], limit: int = 10) -> str:
        """Fetch top Hacker News stories."""
        await ctx.deps.notify("Fetching Hacker News top stories")
        stories = await ctx.deps.hackernews.top_stories(limit=limit)
        return json.dumps(stories, ensure_ascii=False)

    @agent.tool
    async def hn_story(
        ctx: RunContext[AgentDeps],
        item_id: int,
        max_comments: int = 15,
    ) -> str:
        """Fetch a Hacker News story and its top comments by item id."""
        await ctx.deps.notify(f"Fetching HN story {item_id}")
        story = await ctx.deps.hackernews.story_with_comments(item_id, max_comments=max_comments)
        ctx.deps.citations.append(
            {
                "source_type": "hackernews",
                "source_url": story.get("hn_url"),
                "title": story.get("title"),
                "snippet": story.get("text") or story.get("url"),
            }
        )
        return json.dumps(story, ensure_ascii=False)

    @agent.tool
    async def search_memory(
        ctx: RunContext[AgentDeps],
        query: str,
        include_prior_chats: bool = True,
        top_k: int = 6,
    ) -> str:
        """Retrieve relevant past chat messages and ingested file chunks."""
        await ctx.deps.notify("Searching personal memory / files")
        chunks = await ctx.deps.history.search(
            user_id=ctx.deps.user_id,
            chat_id=ctx.deps.chat_id,
            query=query,
            include_prior_chats=include_prior_chats,
            top_k=top_k,
        )
        payload = [
            {
                "source": c.source,
                "score": round(c.score, 3),
                "content": c.content,
                "chat_id": c.chat_id,
                "message_id": c.message_id,
                "document_id": c.document_id,
            }
            for c in chunks
        ]
        return json.dumps(payload, ensure_ascii=False)

    @agent.tool
    async def get_recent_chat_history(ctx: RunContext[AgentDeps], limit: int = 20) -> str:
        """Get recent messages from the current chat for continuity."""
        await ctx.deps.notify("Loading recent chat history")
        messages = await ctx.deps.messages.list_recent(ctx.deps.chat_id, limit=limit)
        payload = [
            {"role": m.role, "content": m.content, "created_at": m.created_at}
            for m in messages
        ]
        return json.dumps(payload, ensure_ascii=False)

    @agent.tool
    async def deep_research(ctx: RunContext[AgentDeps], topic: str) -> str:
        """
        Multi-step deep research: generate queries, fetch sources, dedupe,
        extract facts, compare conflicts, and answer with citations.
        """
        pipeline = DeepResearchPipeline(ctx.deps.settings)
        result = await pipeline.run(ctx.deps, topic)
        return json.dumps(
            {
                "answer": result["answer"],
                "uncertainty_notes": result["uncertainty_notes"],
                "source_count": len(result["sources"]),
                "research_run_id": result["research_run_id"],
            },
            ensure_ascii=False,
        )

    return agent


async def run_agent(
    agent: Agent[AgentDeps, str],
    deps: AgentDeps,
    user_prompt: str,
    message_history: list[dict[str, str]] | None = None,
) -> str:
    """Run agent without streaming; status updates happen via tool callbacks."""
    # Prefetch memory context so personalization happens automatically.
    await deps.notify("Retrieving personal context")
    memory_chunks = await deps.memory.retrieve(
        user_id=deps.user_id,
        chat_id=deps.chat_id,
        query=user_prompt,
    )
    memory_block = deps.memory.format_context(memory_chunks)

    prompt_parts = []
    if memory_block:
        prompt_parts.append(memory_block)
    if message_history:
        compact = "\n".join(
            f"{m['role']}: {m['content']}" for m in message_history[-12:]
        )
        prompt_parts.append(f"Recent conversation:\n{compact}")
    prompt_parts.append(f"User message:\n{user_prompt}")
    full_prompt = "\n\n".join(prompt_parts)

    await deps.notify("Thinking")
    result = await agent.run(full_prompt, deps=deps)
    return result.output


def history_from_messages(messages: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for message in messages:
        if message.role not in {"user", "assistant"}:
            continue
        out.append({"role": message.role, "content": message.content})
    return out


async def persist_citations(
    research_repo,
    *,
    chat_id: int,
    message_id: int,
    citations: list[dict],
) -> None:
    for cite in citations:
        await research_repo.add_citation(
            chat_id=chat_id,
            message_id=message_id,
            research_run_id=None,
            source_type=str(cite.get("source_type") or "web"),
            source_url=cite.get("source_url"),
            title=cite.get("title"),
            snippet=cite.get("snippet"),
        )

# Larplexity

Personal Telegram research assistant powered by **Python 3.12**, **aiogram 3**, **PydanticAI**, and **SQLite**.

## Features

- DeepSeek (or any OpenAI-compatible) LLM via configurable `LLM_BASE_URL`
- PydanticAI tools agent (web search, webpage fetch, HN, memory/RAG, deep research)
- Multi-chat per user: `/new`, `/reset`, `/chats` with pagination + restore buttons
- Restoring/resetting chats does **not** rewrite Telegram history
- Restore auto-sends a session recap
- Status message updated on each tool call (no fake streaming)
- SQLite schema: users, chats, messages, message_chunks, documents, document_chunks, citations, research_runs
- Startup migrations, Docker + healthcheck, structured JSON logs
- Safety: no shell tools, upload path jail, URL SSRF guards, timeouts/retries, per-user rate limits

## Quick start (local)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pypdf   # optional PDF ingestion
cp .env.example .env
# edit .env — set TELEGRAM_BOT_TOKEN, LLM_API_KEY, TAVILY_API_KEY, ALLOWED_USER_IDS
python -m bot
```

Health endpoint: `http://localhost:8080/healthz`

## Docker

```bash
cp .env.example .env
# fill secrets
docker compose up --build -d
docker compose logs -f bot
```

## Commands

| Command | Action |
|---|---|
| `/start`, `/help` | Help |
| `/new` | New conversation |
| `/reset` | Archive current chat, start fresh (Telegram history untouched) |
| `/chats` | Paginated chat list; tap to restore + receive recap |
| `/research <topic>` | Deep multi-step research with citations |

Send text for normal agent chat. Upload `.txt/.md/.csv/.json/.pdf` to ingest into RAG.

## Architecture

```
bot/          aiogram handlers, UX, formatting
agent/        PydanticAI agent + deep research pipeline
tools/        Tavily, webpage, HN, history retrieval
services/     chat/memory/ingest/rate-limit/http
storage/      SQLite + repositories + startup migrations
```

## Configuration

See `.env.example`. Important knobs:

- `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` — OpenAI-compatible provider (DeepSeek default)
- `TAVILY_API_KEY` — web search
- `ALLOWED_USER_IDS` — lockdown for personal use
- `SQLITE_PATH`, `UPLOADS_DIR`

## Memory / RAG

Messages and uploaded files are chunked, hashed into local embeddings (`local-hash-v1`), and stored in SQLite with embedding metadata. Retrieval automatically includes the active chat and recent prior chats so personalization feels automatic.

## Deep research pipeline

1. Generate several search queries
2. Search + fetch multiple sources
3. Deduplicate by URL
4. Extract facts / conflicting claims
5. Answer with inline citations + uncertainty notes

## Safety

- No arbitrary shell execution tools
- Uploads restricted to configured directory + allowlisted extensions
- Webpage fetch blocks private/local hosts
- HTTP timeouts + retries
- In-memory per-user rate limiting

## Development

```bash
pip install -r requirements.txt
python -m pytest -q
```

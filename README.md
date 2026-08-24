# ai-gantt-planner

AI-powered Gantt planner with Excel import, natural language editing via LLM/MCP, and Excel export. Made as a test assignment for Biocad.

## Current scope

- **Frontend** (`frontend/`): full high-fidelity React + TypeScript + Vite UI —
  Import flow, Gantt chart, AI chat panel, change summary, task modal, export.
  Runs in two modes: **mock** (the 12 demo UI states via the dev-only state
  switcher, canned chat responses over the bundled fixtures) and **server**
  (real backend calls for import/get/export, and real AI chat when configured).
- **Backend** (`backend/`): deterministic core (Excel import, scheduler,
  ChangeSet operations, Excel export) **plus** a real AI agent layer —
  OpenRouter (OpenAI-compatible tool calling) + a real Model Context Protocol
  server mounted at `/mcp` inside the same process, exposing exactly 4
  allow-listed tools (`get_project_outline`, `search_tasks`,
  `get_task_details`, `apply_change_set`).
- See `docs/backend-architecture.md`, `docs/backend-contract-audit.md`,
  `docs/mcp-agent-architecture.md`, `docs/agent-system-prompt.md`, and the
  two `docs/spikes/*.md` reports for what was built and verified, and
  `docs/design-system.md` / `docs/design-decisions.md` for the frontend design.

⚠️ **The backend stores everything in memory** — projects and chat history
are both lost on restart, there is no database. This is an explicit MVP
constraint (product-spec §20), not a bug.

## Prerequisites

- Python **3.12** (3.10+ supported) — [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` on Windows
- Node.js 18+ and npm
- (Optional, for real AI chat) an [OpenRouter](https://openrouter.ai/keys) API key and a model id that supports native tool/function calling

## Backend — setup & run (Windows / PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

Health check: `http://localhost:8000/api/v1/health` → `{"status": "ok"}`.
Interactive API docs: `http://localhost:8000/docs`.

Run the backend test suite:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -v
```

This runs everything **except** the live OpenRouter suite (see below) — no
test in the default run makes a real network call to an LLM provider.

To exercise `ChangeSet` operations without the chat/agent layer (curl or the
`/docs` UI), set `ENABLE_DEV_ENDPOINTS=true` in `backend/.env` before
starting the server — this registers a development-only
`POST /api/v1/projects/{project_id}/changes` endpoint. It is **off by
default** and never called by the frontend or the agent (the agent always
goes through MCP, not this endpoint).

### Enabling real AI chat

The app runs completely fine with **no** AI configuration — health, import,
export, and the Gantt all work regardless. Only `POST /chat` needs it, and
degrades cleanly (`503 AI_NOT_CONFIGURED`) without it.

To enable it, add to `backend/.env`:

```env
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=<a model id that supports tool calling, e.g. from openrouter.ai/models>
ENABLE_MCP=true
```

**This spends real, paid OpenRouter usage** the moment a chat message is
sent with these set — there is no sandbox/free mode. `AGENT_MAX_STEPS` (default
6) and `AGENT_MAX_READ_TOOL_CALLS` (default 8) bound worst-case spend per
message; see `backend/.env.example` for all agent-tuning variables and
`docs/mcp-agent-architecture.md` §9 for the full cost-control story.

To run the opt-in live test suite against your real key (also spends real
usage):

```powershell
$env:RUN_LIVE_LLM_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest tests/test_live_agent.py -v
```

## Frontend — setup & run (Windows / PowerShell or any shell)

```powershell
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`. Defaults to `VITE_API_BASE_URL=http://localhost:8000`
(override via `frontend/.env.local`, see `frontend/.env.example`).

Build for production: `npm run build`.

## Trying it end-to-end

1. Start the backend (above) — with or without an OpenRouter key.
2. Start the frontend (above).
3. On the Import screen, drop `frontend/public/sample_patient_card_project.xlsx`
   (or download it via the "Скачать пример Excel" link) and click "Построить план".
4. This is a **real** import against the backend — you'll see the 16-task
   canonical plan with a 2 ноября release date.
5. Type a request in the chat (e.g. "Увеличь Frontend-разработку на 2 дня")
   and send it:
   - **With an OpenRouter key configured** — a real agent turn runs: it
     reads the plan through MCP, applies the change atomically through the
     same validated path the rest of the backend uses, and the Gantt/chat
     update from the real, backend-computed diff.
   - **Without one** — you'll see "AI-редактирование будет подключено на
     следующем этапе" instead, and nothing about the plan changes.
6. Click "DEV" (bottom-right) to jump straight to any of the 12 mock demo
   states — including the full AI-edit "before → after" scenario with the
   9 ноября release date — without needing the backend or an OpenRouter key
   at all.

## AI chat status

The chat panel is fully designed and interactive in **mock mode** (12 demo
states, reachable via the DEV switcher or by typing) — this never touches
the backend and never costs anything. In **server mode**, real
natural-language editing is now implemented end-to-end: `POST /chat` →
`AgentService` → OpenRouter (tool calling) → the real MCP server mounted at
`/mcp` → the same `ProjectService.apply_change_set()` the rest of the
backend already uses. Supported edits are exactly the `ChangeSet` operations
product-spec §14 defines (rename, change duration, move, create, insert
between, set/add/remove dependencies, bulk-assign, clear a start
constraint) — the agent combines everything a single message asks for into
one atomic change set, at most one per message.

Known limitation: this has been verified thoroughly against a scripted fake
model (32 backend tests, zero network calls — see
`docs/spikes/mcp-agent-report.md`) and against real backend response shapes
end-to-end through the frontend, but **not against a real OpenRouter call in
this session** — no API key was available. The live test suite
(`tests/test_live_agent.py`) exists and is ready to run the moment one is
provided.

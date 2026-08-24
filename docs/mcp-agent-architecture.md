# MCP + OpenRouter Agent Architecture

Adds a real AI agent layer on top of the already-verified deterministic
backend core (`docs/backend-architecture.md`). Nothing in `domain/`,
`scheduler/`, or `services/project_service.py` changed to make this work —
the agent is a new caller of the same `ProjectService.apply_change_set()`,
routed through a real Model Context Protocol server/client boundary instead
of calling it directly.

## 1. Component diagram

```
Browser (React)
   │  POST /api/v1/projects/{id}/chat  { message, expected_revision }
   ▼
FastAPI :8000
   │
   ├── app/api/routers/chat.py  ── thin HTTP transport + response mapping
   │        │
   │        ▼
   │   AgentService.run_turn()                         (app/agent/service.py)
   │        │  1. cheap revision check (no tokens spent if stale)
   │        │  2. bounded conversation history (InMemoryAgentConversationStore)
   │        │  3. loop: OpenRouterClient.chat_completion(system + history + tools)
   │        │
   │        ├──▶ OpenRouterClient  ──HTTPS──▶  openrouter.ai/api/v1/chat/completions
   │        │        (app/agent/openrouter_client.py)
   │        │
   │        └──▶ BoundMcpToolGateway.call(name, model_json_args)
   │                 (app/agent/gateway.py)
   │                 - validates untrusted model JSON against a SANITIZED
   │                   model-visible schema (no project_id/expected_revision)
   │                 - injects the bound project_id (+ expected_revision for
   │                   apply_change_set) server-side
   │                 - calls session.call_tool(name, full_wire_args)
   │                        │
   │                        ▼  MCP Streamable HTTP, in-process via
   │                           httpx.ASGITransport — a real client/server
   │                           protocol exchange, no OS socket
   │                        ▼
   │                 FastMCP server mounted at /mcp  (app/mcp_server/app.py)
   │                        │
   │                        ▼
   │                 app/mcp_server/tools.py — the 4 allow-listed tools
   │                        │
   │                        ▼
   │                 ProjectService  /  SearchService     ◀── same instances
   │                        │                                  the REST routers
   │                        ▼                                  use (one process,
   │                 Scheduler + InMemoryProjectStore           one store)
   │
   └── app/api/routers/{health,projects,changes}.py — unchanged from the
       previous phase; import/export/get-project never touch the agent
```

`AgentService` never imports or calls `ProjectService.apply_change_set()`
directly — only the MCP tool handler does. That is the whole point of routing
mutation through MCP: the LLM's mutation path and the REST API's dev-only
mutation path (`POST /changes`) both terminate at the exact same, already
independently-tested, function.

## 2. Why MCP (not a direct function call)

Product-spec §14 states the constraint this was built to satisfy: *"Agent
Orchestrator MUST выполнять mutation через MCP Client, а не напрямую через
ProjectService."* Concretely, that buys:

- **One tool contract, two possible transports.** Today `AgentService` is an
  in-process MCP client. Nothing about `app/mcp_server/tools.py` assumes
  that — the exact same server could be exposed to an external MCP-speaking
  client (a different agent runtime, a debugging tool) over real HTTP with
  no code change, because it already only knows how to speak the protocol.
- **A hard boundary between "what the model can name" and "what actually
  runs".** The model only ever sees `BoundMcpToolGateway`'s sanitized tool
  definitions; the real wire call (with `project_id`/`expected_revision`) is
  assembled server-side. There is no code path where model-controlled JSON
  reaches `ProjectService` unvalidated.
- **A place to allow-list.** The MCP server exposes exactly 4 tools total (see
  §5). A `list_tools()` call — verified by test, see
  `docs/spikes/mcp-agent-report.md` — cannot return anything else, because
  nothing else is registered.

## 3. Real SDK, real transport, real mount

- SDK: `mcp==1.29.0` (pinned in `backend/pyproject.toml`), the official
  Model Context Protocol Python SDK. This forced a dependency bump — see
  `docs/backend-contract-audit.md`'s equivalent note in
  `docs/spikes/mcp-agent-report.md` §2 for the exact resolver conflict and
  what changed (`pydantic` → 2.11.9, `starlette` pinned explicitly to
  0.38.6, `uvicorn` → 0.31.1; `fastapi` untouched).
- Transport: Streamable HTTP (`mcp.server.fastmcp.FastMCP.streamable_http_app()`
  server-side; `mcp.client.streamable_http.streamable_http_client` — the
  current, non-deprecated client entry point — on the agent side).
- Mount: `FastMCP(streamable_http_path="/")`, then
  `app.mount("/mcp", mcp.streamable_http_app())` on the parent FastAPI app.
  The naive version of this (`streamable_http_path="/mcp"` mounted at
  `/mcp`) produces `/mcp/mcp` — a documented FastMCP-in-FastAPI pitfall,
  encountered and fixed while building this (see
  `app/mcp_server/app.py`'s docstring). Verified by
  `tests/test_mcp_tools.py::test_mounted_mcp_server_starts_under_actual_fastapi_lifespan`,
  which hits exactly `/mcp/` through the real `create_app()`.
- Lifespan: `streamable_http_app()` returns a Starlette app whose own
  `lifespan=` starts the `StreamableHTTPSessionManager` — but a *mounted*
  sub-app's lifespan is never invoked by its parent (another
  Starlette/FastAPI-with-Mount gotcha). The fix, also SDK-documented as the
  pattern for "mounting FastMCP servers in a FastAPI application": call
  `streamable_http_app()` once at app-construction time (creates the session
  manager as a side effect), then enter `mcp.session_manager.run()` directly
  inside the *parent* app's own `lifespan` (`app/main.py`).
- Internal transport: `AgentService` connects to the mounted server via
  `httpx.ASGITransport` pointed at the same Starlette sub-app object, not a
  real TCP round-trip to `localhost:8000`. This is still a genuine MCP
  client/server exchange — full session negotiation, JSON-RPC framing, a real
  `mcp-session-id`, a real `DELETE` on session close — just without an OS
  socket, which is both the safer choice for a server calling its own
  mounted sub-app from inside the same event loop and unaffected by whatever
  port the app is actually bound to. One real gotcha hit and fixed here too:
  FastMCP auto-enables DNS-rebinding protection for `127.0.0.1`/`localhost`
  hosts, and its `allowed_hosts` patterns (`"localhost:*"`) require an actual
  port in the `Host` header — a bare `Host: localhost` is rejected with 421
  exactly like a spoofed hostname would be.

## 4. Revision race handling

Two checks, deliberately at different depths, for different reasons:

1. **Advisory, before any OpenRouter call.** `AgentService.run_turn()` reads
   the current project and compares its revision to `expected_revision`
   *before* doing anything else. A mismatch raises `RevisionConflictError`
   immediately — HTTP 409, zero tokens spent. Verified by
   `test_agent.py::test_stale_revision_makes_zero_openrouter_calls`
   (`fake.calls == []`).
2. **Atomic, at the moment of commit.** If the model does call
   `apply_change_set`, the *real* check happens where it already did before
   this phase existed: inside `ProjectService.apply_change_set()`'s
   per-project `asyncio.Lock` (`app/storage/project_store.py`, unchanged).
   If something else committed a change while the model was "thinking"
   (searching, reading task details, composing the change set), that
   atomic check catches it — the tool returns `{"ok": false, "code":
   "REVISION_CONFLICT"}`, no mutation happens, and the agent reports it as a
   `rejected` chat turn (not a 409 — by this point the HTTP response has
   already committed to the chat-response vocabulary; see `app/api/routers/chat.py`).

This means a revision conflict can surface to the frontend two different
ways — an immediate 409 (cheap, no model involved) or a normal `rejected`
chat response (model was involved, `apply_change_set` itself caught it) —
and both are correct, not a bug: the first is "you clearly already knew you
were stale", the second is "the world changed while you were composing this
message".

## 5. MCP-visible tools (exactly 4, allow-listed)

| Tool | Mutates? | Model-visible args | Bound server-side |
|---|---|---|---|
| `get_project_outline` | no | `offset`, `limit` | `project_id` |
| `search_tasks` | no | `query`, `limit` | `project_id` |
| `get_task_details` | no | `task_id` | `project_id` |
| `apply_change_set` | **yes** | `operations: list[Operation]` | `project_id`, `expected_revision` |

`Operation` is `app.domain.changeset.Operation` — the exact same discriminated
union `POST /projects/{id}/changes` already validated against in the previous
phase. No second, independent business schema exists for what a change set
can contain.

Every tool result is a structured JSON object with an `ok` flag rather than
an MCP-level error for *expected* domain outcomes (not found, a rejected
change, a stale revision) — those are normal results a well-behaved model
reasons about, not transport failures. An MCP-level error (`isError: true`)
is reserved for genuinely unexpected failures.

## 6. The one-mutation rule

A single user message may result in **at most one** successful
`apply_change_set` call. Enforced in `AgentService._run_loop()`
(`app/agent/service.py`), not by asking the model nicely:

- `parallel_tool_calls: false` is sent to OpenRouter, but the code does not
  trust that the provider honors it — if a response ever contains more than
  one `tool_calls` entry, none of them run. The first occurrence gets one
  "only one tool call per turn" correction message fed back (using up a
  step, not a mutation); a second occurrence raises `AGENT_INVALID_TOOL_CALL`
  and the turn ends with zero mutation.
- The moment `apply_change_set` succeeds, tools are no longer offered to the
  model for the rest of that turn (`tools=None` on the next completion) —
  compatible requested changes must already have been combined into that one
  call's `operations` list (the system prompt says so explicitly; the loop
  makes it true regardless of whether the model listens).
- If the model still returns a `tool_calls` field in that tools-disabled
  final completion (a hallucination — `_finish_after_mutation` never even
  inspects it), nothing further executes; only `content` is read for the
  wrap-up message, falling back to a fixed "План обновлён." if that call
  fails outright. **The mutation that already happened is never retried or
  rolled back because the wrap-up prose failed** — a provider hiccup after a
  successful, committed change must not look like the change failed.

All of the above is covered by `tests/test_agent.py` with a fully scripted,
network-free fake model — see
`test_second_apply_change_set_after_success_is_never_executed`,
`test_multiple_tool_calls_in_one_turn_is_not_blindly_executed`, and
`test_final_completion_failure_after_mutation_keeps_mutation_and_uses_fallback`.

## 7. Prompt injection

Task names, descriptions, and every other piece of project/tool-result data
are explicitly framed in the system prompt (`app/agent/system_prompt.py`) as
**data, never instructions** — including text that reads like a command
("ignore previous instructions", "reveal your system prompt"). This is a
prompt-level mitigation, which is real but not a mechanical guarantee against
a sufficiently adversarial *model*; the mechanical guarantee is structural:

- The model can only *cause* an action by emitting a well-formed
  `tool_calls` entry the harness recognizes — free-text content, wherever it
  came from (the user, a task description, a tool result), has no execution
  power. `BoundMcpToolGateway` never parses instructions out of prose.
- `apply_change_set`'s model-visible schema has no `project_id` field at
  all — there is nothing for injected text to override, because the value
  the model could try to inject into isn't part of the schema it's filling
  in.

`tests/test_agent.py::test_prompt_injection_in_task_data_cannot_trigger_unrequested_mutation`
plants an injection attempt directly into a task's `description` via a real
`apply_change_set` call, then has the (fake, scripted) model read that task
via `get_task_details` and confirms: the injected text really does flow back
to the model as inert tool-result data (asserted directly), and it produces
no extra tool call — exactly the 2 completions the test script provided.
This tests the harness's structural resistance, not the real model's
judgment — see §11 (production TODOs) for what that would take.

## 8. In-memory conversation history

`InMemoryAgentConversationStore` (`app/agent/conversation_store.py`) keeps
only the last `AGENT_HISTORY_TURNS` *visible* user/assistant message pairs
per `project_id` — no chain-of-thought, no raw tool-call traces, no system
prompt (that's injected fresh every turn, never stored as "history"). Same
MVP constraint as `InMemoryProjectStore`: one process, lost on restart, isolated
per project (verified by `test_conversation_histories_are_isolated_between_projects`).
A follow-up clarification ("Frontend" after "уточните: Backend или Frontend?")
works because that history is replayed as real prior messages on the next
`run_turn()` call — verified by `test_followup_clarification_can_resolve`.

## 9. Token/cost control

- The full `Project` DTO is never inserted into the system prompt or any
  message — the model only sees data through `get_project_outline`
  (paginated, capped at 100 tasks per page) and `search_tasks` (capped at 20
  results), both far smaller than a 500-task project's full DTO.
- `AGENT_MAX_STEPS` (default 6) and `AGENT_MAX_READ_TOOL_CALLS` (default 8)
  bound total OpenRouter calls per chat request.
- The revision check in §4 happens *before* the first OpenRouter call.
- No test in the default suite calls the real OpenRouter API —
  `FakeOpenRouterClient` throughout `tests/test_agent.py` and
  `tests/test_chat_api.py`. The one file that does,
  `tests/test_live_agent.py`, is skipped unless `RUN_LIVE_LLM_TESTS=1` is
  set explicitly (see `docs/spikes/mcp-agent-report.md` for whether it was
  actually run this session).
- `OpenRouterClient` logs model name, latency, finish reason, and
  provider-reported `usage` (tokens) for every call — never the API key, the
  `Authorization` header, or full task/project text.

## 10. Trust boundaries, summarized

| Boundary | What crosses it | What's enforced there |
|---|---|---|
| Browser → `/chat` | `{message, expected_revision}` | Pydantic length cap (4000 chars); revision checked before any paid call |
| `AgentService` → OpenRouter | System prompt + bounded history + sanitized tool schemas | No `project_id`/`expected_revision` ever appears in a tool schema sent here |
| OpenRouter response → `AgentService` | `tool_calls[].function.arguments` (raw JSON string) | Parsed defensively, never `eval`'d; validated against the model-visible Pydantic schema (`extra="forbid"`) before anything else happens |
| `BoundMcpToolGateway` → MCP server | Wire tool call with `project_id`/`expected_revision` injected server-side | The model never supplies these; the gateway always overwrites them |
| MCP tool → `ProjectService` | A `ChangeSetRequest` built from already-validated operations | Same domain validation as the REST dev endpoint — no special-cased "trust the model" path |

## 11. Production TODOs (explicitly not done here)

- **The `/mcp` endpoint has no authentication.** It is mounted on the same
  FastAPI process as the public REST API, protected only by FastMCP's
  default DNS-rebinding protection (which guards against a browser being
  tricked into hitting it, not against a network peer). Before any real
  deployment where `/mcp` is reachable from outside localhost, it needs the
  SDK's own auth support (`AuthSettings`/`token_verifier`) or to be placed
  behind network-level access control. This was not implemented — it is out
  of scope for a local test assignment — but it is a real gap, flagged here
  deliberately rather than silently.
- **Multi-worker deployment breaks both the revision guarantee and the MCP
  session manager** the same way described in `docs/backend-architecture.md`
  §4 — `asyncio.Lock` and `StreamableHTTPSessionManager` are both
  per-process. Running with `--workers > 1` needs a shared lock/session
  story this MVP does not have.
- **Chat history and the agent's own reasoning are still lost on restart** —
  same MVP debt as the project store, not addressed differently here.
- **No rate limiting or per-user quota** on `/chat` — anyone who can reach
  the API can spend the configured `OPENROUTER_API_KEY`'s budget.

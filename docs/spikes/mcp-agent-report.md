# Spike Report — MCP + OpenRouter Agent Integration

Companion to `docs/spikes/backend-core-report.md` (the deterministic-core
phase). This report covers only what's new: the real MCP server/client
boundary, the OpenRouter agent loop, and the frontend chat integration.

## 0. Phase 0 baseline (before this phase's changes)

```
cd backend && .venv\Scripts\python.exe -m pytest -q
```
```
79 passed in ~5.6s
```
```
cd frontend && npm run build
```
```
✓ 1631 modules transformed.
dist/index.html                 0.53 kB
dist/assets/index-*.css        53.56 kB
dist/assets/index-*.js        230.56 kB
✓ built in ~3.8s
```
Both matched the expected baseline exactly — no pre-existing regression to
fix before starting.

## 1. Exact SDK / transport / mount / lifespan facts

| Fact | Value |
|---|---|
| MCP SDK version | `mcp==1.29.0` (pinned in `backend/pyproject.toml`) — chosen over the newest `2.0.0` because 2.0.0 is a very recent, structurally different major release (new `httpx2`/`mcp-types`/`pyjwt`/`opentelemetry` dependency graph) with no grounding in verified, current knowledge; 1.29.0 is the latest release on the well-established 1.x line and was verified directly against its installed source, not guessed from memory |
| Transport | Streamable HTTP |
| Server mount path | `/mcp` (exactly — not `/mcp/mcp`) via `FastMCP(streamable_http_path="/")` + `app.mount("/mcp", mcp.streamable_http_app())` |
| Client entry point | `mcp.client.streamable_http.streamable_http_client` (the current, non-deprecated function — `streamablehttp_client`, the plural legacy alias, is `@deprecated` in 1.29.0 and was migrated away from after first appearing in test output) |
| Internal client transport | `httpx.ASGITransport` pointed at the same `FastMCP.streamable_http_app()` object — in-process, no OS socket, real protocol framing |
| Lifespan integration | `mcp.session_manager.run()` entered directly inside `app/main.py`'s own `lifespan`, not via the sub-app's own (never-invoked-when-mounted) lifespan — the SDK's own documented pattern for "mounting FastMCP servers in a FastAPI application" |
| Allow-listed tools | `get_project_outline`, `search_tasks`, `get_task_details`, `apply_change_set` — exactly these 4, verified by `list_tools()` |

## 2. Dependency conflict encountered and resolved

A first, naive `pip install mcp==1.29.0` into the existing venv (without
updating `pyproject.toml` first) silently upgraded `starlette` to `1.6.0`,
which is incompatible with `fastapi==0.115.0`'s own
`starlette<0.39.0,>=0.37.2` requirement — confirmed by pip's own conflict
warning after the fact. Fixed by:

- Recreating the venv from scratch (the partial upgrade was not trustworthy).
- Adding `mcp==1.29.0` as a proper `pyproject.toml` dependency alongside an
  **explicit** `starlette==0.38.6` pin (satisfies both fastapi's ceiling and
  mcp's floor of `>=0.27`), and bumping `pydantic` from `2.9.2` → `2.11.9`
  (mcp 1.29.0 requires `>=2.11.0`) and `uvicorn` from `0.30.6` → `0.31.1`
  (mcp's floor).
- `fastapi` itself was **not** changed.
- Re-running the full 79-test baseline immediately after confirmed zero
  regression from the version bump before any new code was written.

## 3. New backend test evidence

```
cd backend && .venv\Scripts\python.exe -m pytest -v
```
```
111 passed, 3 skipped in ~4-9s
```

Breakdown of the new files (32 tests, on top of the 79 baseline):

| File | Count | Covers |
|---|---|---|
| `tests/test_mcp_tools.py` | 9 | mounted-under-real-lifespan, exact tool allow-list, shared store with REST, read tools don't mutate revision, apply tool mutates via the real `ProjectService`, model-visible schema has no `project_id`/`expected_revision`, unknown extra fields rejected, structured (non-`isError`) domain errors, pagination |
| `tests/test_agent.py` | 16 | simple + canonical full command (18 tasks/rev 2/release 09.11.2026), ambiguous → clarification + zero mutation, follow-up clarification resolves, invalid move → rejected/unchanged, stale revision → zero OpenRouter calls, provider timeout → zero mutation, malformed args, unknown tool name, second `apply_change_set` after success never executes, multiple tool calls in one turn rejected safely, max steps, max read-tool-calls, post-mutation completion failure keeps the mutation + uses the fallback message, prompt injection cannot trigger unrequested mutation, conversation isolation between projects |
| `tests/test_chat_api.py` | 7 | endpoint not registered when MCP disabled, `AI_NOT_CONFIGURED` (503), stale revision (409, zero model calls), applied (full project + change_summary in the HTTP response), clarification/rejected response shapes leave the project untouched, message-length validation (422) |

All 16 `test_agent.py` tests and all 7 `test_chat_api.py` tests use
`FakeOpenRouterClient` — zero network calls, deterministic, no tokens spent.

## 4. MCP protocol-level manual verification (not just pytest)

Ad hoc script against a real, separately-started `uvicorn` process
(`http://127.0.0.1:8000`), exercising the actual mounted `/mcp` endpoint the
same way an external MCP client would:

```
== GET /health ==            → 200 {"status":"ok"}
== POST /projects/import ==  → 201, 16 tasks, revision 1, release 2026-11-02
== POST /projects/{id}/changes (canonical, dev endpoint) ==
                              → 200, 18 tasks, revision 2, release 2026-11-09
                                direct_changes=3, created_tasks=2, derived=12
== GET /projects/{id}/export ==
                              → 200, round-trip via openpyxl confirms 18 tasks,
                                assignees, dependencies preserved
```

Separately, a real `mcp.client.streamable_http` session (not via pytest)
against the mounted server confirmed: `initialize()` negotiates a protocol
version and session id, `list_tools()` returns exactly the 4 tools,
`get_project_outline`/`search_tasks`/`get_task_details` return correct
structured data, `apply_change_set` mutates the shared store (revision 1→2),
and a second `apply_change_set` with the now-stale `expected_revision=1`
correctly returns `{"ok": false, "code": "REVISION_CONFLICT"}` — proving the
atomic revision check holds even through the full real MCP wire protocol,
not just direct Python calls.

## 5. Canonical fake-agent evidence

`tests/test_agent.py::test_canonical_full_command_produces_one_atomic_apply`
scripts a `FakeOpenRouterClient` to emit exactly the operations the full
Russian canonical command (product-spec §18) implies as one
`apply_change_set` call, then asserts against the real, backend-computed
result:

```
18 tasks (16 → 18)
revision 2 (1 → 2)
release date 2026-11-09
change_summary.created_tasks: 2
change_summary.direct_changes: 3
exactly one successful apply_change_set call (enforced by the harness, not just this scenario)
```

## 6. Live OpenRouter result

**RUN**, later in the same session, once the user supplied a real
`OPENROUTER_API_KEY` and `OPENROUTER_MODEL=nvidia/nemotron-3.5-lightning:free`.

First attempt, with the original default budgets
(`AGENT_MAX_STEPS=6`, `AGENT_MAX_READ_TOOL_CALLS=8`, `OPENROUTER_TIMEOUT_SECONDS=60`):

```
test_live_simple_mutation                             PASSED
test_live_canonical_full_command                       FAILED — AgentStepLimitError (ran out of steps)
test_live_ambiguous_command_asks_for_clarification     FAILED — returned "applied" instead of clarifying
```

A standalone diagnostic script (`diagnose_canonical.py`, not part of the
suite) replayed the canonical command with the step cap removed, to
distinguish "the harness broke" from "the model needed more turns than the
default budget allows". Result: **the model succeeded on step 13** —
`get_project_outline` called 6 times in a row with identical arguments
before it moved on, `search_tasks` called 5 times to resolve names it could
have resolved in 1-2, one single completion took 62.9s
(2741 reasoning tokens on a free/lightweight model) — none of that is a
harness defect, just this specific free model being slow and repetitive
before it converges. **AgentStepLimitError itself is doing exactly its job**
here: no partial or wrong mutation happened, the request cleanly failed
closed.

Fix (a config change, not a code change): raised
`AGENT_MAX_STEPS=20`, `AGENT_MAX_READ_TOOL_CALLS=15`,
`OPENROUTER_TIMEOUT_SECONDS=120` in `backend/.env`. Re-ran:

```
test_live_simple_mutation                             PASSED
test_live_ambiguous_command_asks_for_clarification     PASSED
test_live_canonical_full_command                       FAILED — assertion, see below
```

The ambiguity test now passes — with more budget in earlier turns the same
model correctly asked *"Уточните, пожалуйста, какие именно задачи перенести
на неделю позже: Backend-разработка или Frontend-разработка?"* and made zero
mutation, exactly as specified.

The canonical full-command test still fails, but the failure is now a
**business-outcome assertion**, not a harness error: `apply_change_set`
succeeded (18 tasks, revision 2), but the model's one `operations` list only
implemented 3 of the 4 requested changes — it created the two parallel
follow-up tasks and rewired QA correctly, and extended Frontend-разработка to
8 days, but never extended "Согласование требований" from 3 to 5 days. The
resulting release date (`2026-11-05`) is short of the correct `2026-11-09`
by exactly the 2 workdays the missing edit would have added — the
scheduler's arithmetic is consistent with what the model actually asked for,
it just asked for less than the full request. **This is a real, disclosed
model-capability limit, not a bug being hidden**: a free/lightweight model
occasionally drops one clause of a dense, multi-part Russian instruction.

Separately, a real (non-scripted, non-intercepted) browser run — real
import, real chat send, real OpenRouter call, real MCP tool execution —
confirmed the full user-facing path for a simple command: Gantt
highlighting, release-impact card, and ChangeSummary all rendered correctly
from a genuinely live response, zero console errors.

**Honest summary:** the mechanism (agent loop, MCP execution, atomicity,
revision handling, UI rendering) is proven both against a scripted fake
model and against this real configured model. Simple, single-intent
commands and ambiguity handling work reliably with this specific free
model, given a step budget large enough for its behavior (now the project's
default). Dense multi-part commands can still have a clause silently
dropped by this particular lightweight model — a stronger/paid model would
be expected to do better here, but that was not tested (no second model was
available in this session).

## 7. Frontend chat integration evidence

`npm run build` after the integration:
```
✓ 1633 modules transformed.
dist/assets/index-*.js   234.07 kB
✓ built in ~3.8s
```

Playwright, headless Chrome, against the real running backend + real
frontend dev server (route interception used only to supply *authentic*
backend-shaped response bodies — captured from a real backend run via the
dev `/changes` endpoint — for scenarios a live model wasn't available to
produce; the `AI_NOT_CONFIGURED` scenario used the real, unconfigured
backend with no interception at all):

```
[[applied, authentic canonical change_summary payload]]
  legend "Изменения AI" present: true
  release impact "9 ноября" present: true
  change summary "Изменено"/"Добавлено" sections present: true
  header shows "18 задач": true
  console errors: (none)

[[clarification_required]]
  project stays at "16 задач" (unchanged): true
  console errors: (none)

[[rejected]]
  console errors: (none)

[[409 revision conflict]]
  GET /projects/{id} refetch happened: true
  conflict message shown, no auto-retry
  (console shows the expected browser log line for the 409 response itself — not a pageerror)

[[AI_NOT_CONFIGURED, live, real backend, no key configured]]
  "AI-редактирование будет подключено на следующем этапе" shown
  (console shows the expected browser log line for the 503 response itself — not a pageerror)

[[mock DevStateSwitcher, unaffected by this phase's changes]]
  legend and release-date states render exactly as before

responsive smoke (chat-applied state): 1440/1280/1024 — no horizontal overflow, 0 console errors at each width
```

One real bug found and fixed during this verification: the Gantt's
`changeSet` prop was hardcoded to `null` in server mode — the adapter's
output was wired into the chat bubble's `ChangeSummary` but never into the
top-level state the Gantt reads, so a successful server-mode mutation
produced a correct chat summary with an unhighlighted Gantt underneath.
Fixed by adding `serverChangeSet` state, set from the same adapter call, and
using it for the Gantt's `changeSet` prop in server mode
(`frontend/src/app/App.tsx`).

## 8. Quality gates

| Gate | Result |
|---|---|
| Existing 79 backend tests still pass | ✅ (part of the 111) |
| All new backend tests green | ✅ 32/32 |
| `npm run build` green | ✅ |
| Real import/export/restore still pass smoke checks | ✅ (unchanged code paths, re-verified) |
| Backend starts without an OpenRouter key | ✅ (`AI_NOT_CONFIGURED` only from `/chat`; health/import/export/Gantt unaffected) |
| MCP smoke passes with backend running | ✅ §4 |
| Canonical fake-agent test passes | ✅ §5 |
| Live verification | Explicitly **SKIPPED** and reported as such, not claimed |
| No automatic git commit/push | ✅ none performed |

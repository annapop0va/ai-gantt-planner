# Backend Architecture

Deterministic backend core for AI Gantt Planner: Excel import, scheduling,
change-set application, Excel export. No OpenRouter, no LLM, no MCP yet —
see the "Next phase" section at the end for exactly where that plugs in.

## 1. Stack

- Python 3.12 (minimum supported: 3.10, per `backend/pyproject.toml`)
- FastAPI 0.115 + Uvicorn (ASGI)
- Pydantic v2 (domain models *and* wire schemas — one validation library, no duplication)
- openpyxl 3.1 (`.xlsx` read/write)
- pytest 8.3 + httpx (via `fastapi.testclient.TestClient`)

One dependency file: `backend/pyproject.toml` (`[project.dependencies]` for
runtime, `[project.optional-dependencies].dev` for test tooling). No
`requirements.txt`, no second lockfile competing with it.

## 2. Module layout

```
backend/app/
├── main.py            FastAPI app factory: lifespan, CORS, exception handlers, router registration
├── settings.py         Pydantic-settings: APP_ENV, FRONTEND_ORIGINS, ENABLE_DEV_ENDPOINTS
├── api/
│   ├── deps.py          FastAPI dependency providers (store, service, settings) — no module globals
│   ├── errors.py         DomainError -> {code, message, details} JSON, never leaks a stack trace
│   └── routers/
│       ├── health.py      GET /api/v1/health — no store dependency at all
│       ├── projects.py    POST import, GET project, GET export
│       └── changes.py     POST .../changes — dev-only, conditionally registered
├── domain/              Framework-free. No FastAPI import anywhere in this package.
│   ├── models.py          Project, Task (Pydantic models used as the in-process domain type)
│   ├── constants.py       HOURS_PER_WORKDAY, MIN/MAX_DURATION_WORKDAYS, MAX_TASKS, MAX_FILE_SIZE_BYTES, …
│   ├── normalize.py       normalize_name() — trim/collapse/casefold/ё-е
│   ├── changeset.py       TaskRef + the 10 operation shapes (transport-agnostic)
│   ├── diff.py            compute_change_summary(before, after) -> ChangeSummary
│   └── errors.py          DomainError hierarchy with stable `code` + HTTP `status`
├── scheduler/            Framework-free. Pure date arithmetic over a dependency graph.
│   ├── calendar.py         Mon-Fri workday arithmetic (no holidays)
│   ├── calendar_shift.py   signed workday shift (move_task can go earlier)
│   └── engine.py           compute_schedule(tasks, project_start_date) -> dates + warnings
├── services/             Orchestration. The only layer that touches more than one of the above.
│   ├── excel_import.py     .xlsx bytes -> unscheduled Task[] + warnings
│   ├── excel_export.py     Project -> .xlsx bytes
│   ├── changeset_ops.py    ChangeSetApplier — applies the 10 operations to a working-copy Task[]
│   └── project_service.py  import_project / get_project / apply_change_set / export_project
├── storage/
│   └── project_store.py   InMemoryProjectStore — per-project asyncio.Lock, revision-checked-in-lock
└── schemas/              The only place a domain object becomes an HTTP response body.
    ├── common.py           ErrorResponse
    ├── project.py           ProjectOut/TaskOut + project_to_out() (computes successor_ids here)
    └── changeset.py          ChangeSetResponse
```

## 3. Data flow

### Import

```
UploadFile (capped read, ≤5MB)
  -> ExcelImportService.parse()          openpyxl bytes -> unscheduled Task[] + row-level warnings
  -> compute_schedule()                  assigns start_date/end_date, revision=1
  -> InMemoryProjectStore.create()
  -> project_to_out()                    Project -> ProjectOut (adds successor_ids)
  -> 201 ImportResponse{project, warnings}
```

Row-level errors are collected across the *entire* sheet (not just the first)
and raised together as one `ImportValidationError` with a `details: [{row,
field, code, message}, …]` list — the router never sees a partially-built
project on failure; nothing is stored.

### Change set (dev endpoint only, today)

```
ChangeSetRequest{expected_revision, operations[]}
  -> InMemoryProjectStore.apply(project_id, expected_revision, mutator)
       [inside the per-project lock:]
       -> re-read current revision, compare to expected_revision       (REVISION_CONFLICT if stale)
       -> deep-copy tasks (working copy) — original untouched until commit
       -> ChangeSetApplier.apply_all(operations)                       (any DomainError aborts everything)
       -> compute_schedule(applied_tasks, project.project_start_date)
       -> commit: revision += 1, updated_at = now
  -> compute_change_summary(before_snapshot, new_project)              (before/after diff, not tracked-during-apply)
  -> 200 ChangeSetResponse{status: "applied", project, change_summary, warnings}
```

The revision check happens *inside* the lock (`InMemoryProjectStore.apply`),
not before it — two concurrent requests against the same stale revision can
never both commit, even though this is still a single-process/single-worker
store (see §4).

### Export

```
InMemoryProjectStore.get(project_id)
  -> ExcelExportService.export()     openpyxl Workbook -> bytes (План + Метаданные sheets)
  -> Response with Content-Disposition (RFC 5987 UTF-8 filename) + expose_headers so browser fetch() can read it
```

## 4. Storage & concurrency constraints (explicit, not hidden)

- `InMemoryProjectStore` lives on `app.state.project_store`, created fresh in
  the `lifespan` context — never a module-level global.
- One `asyncio.Lock` per project id. `apply()` acquires the lock, re-reads
  the current revision, validates, mutates a working copy, and only then
  commits — all inside the same critical section.
- This still assumes **one process, one worker**. `asyncio.Lock` only
  serializes coroutines within a single event loop; running Uvicorn with
  `--workers > 1` (or behind a multi-process supervisor) would give each
  worker its own store and its own locks, silently breaking the revision
  guarantee. Acceptable for the MVP per product-spec §20; flagged here so
  the next phase doesn't discover it by breaking.
- All state is lost on restart. There is no persistence layer. The frontend
  copes with this explicitly (see `docs/backend-contract-audit.md` §3 and
  the reload-restore flow in `App.tsx`): a lost project after a backend
  restart shows a clear "load the file again" screen, not a silent failure.

## 5. The two diff shapes, side by side

Two different "what changed" representations exist on purpose, for two
different audiences:

| | `app/domain/diff.py::ChangeSummary` (backend) | `frontend/src/lib/diff.ts::ChangeSet` (frontend mock) |
|---|---|---|
| Audience | API consumer / test assertions / a future MCP tool result | The Gantt highlight index and the chat `ChangeSummary` card |
| Shape | `direct_changes` / `created_tasks` / `dependency_changes` / `derived_schedule_changes`, each field-delta flat | `byTask` (per-id classification for O(1) Gantt lookup), grouped `modified`/`created`/`derived`, plus `release: ReleaseImpact \| null` |
| Computed from | `before`/`after` `Project` snapshots (backend types) | `before`/`after` `Project` snapshots (frontend types, currently always the two fixtures) |

No adapter converts one into the other today — see
`docs/backend-contract-audit.md` §4 item 5 for why building one now would be
speculative. When real chat responses replace the mock, that adapter is the
first thing the next phase should write, informed by whatever shape the
actual chat/MCP response turns out to need.

## 6. Next phase: MCP + OpenRouter

`ProjectService.apply_change_set()` is the seam. Product-spec §14 already
states the constraint this architecture was built to satisfy: "Agent
Orchestrator MUST выполнять mutation через MCP Client, а не напрямую через
ProjectService" — i.e., the MCP *tool* implementation calls
`ProjectService.apply_change_set()` exactly the way `app/api/routers/changes.py`
does today, just from a tool handler instead of an HTTP route. Nothing in
`domain/`, `scheduler/`, or `services/` needs to change for that; only a new
router (a real `/chat` endpoint) and the MCP tool boundary itself are new
work.

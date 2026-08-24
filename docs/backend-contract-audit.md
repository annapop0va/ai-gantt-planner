# Backend Contract Audit (Phase 0)

Written before backend work is considered "done" — captures what the existing
frontend actually expects, where it differs from the illustrative shapes in
the integration prompt, and the minimal-adapter decisions made as a result.
No blocking contradiction was found; every difference below was resolved with
an adapter rather than a frontend redesign or a product-spec change.

## 1. Starting state (`git status` at the start of this phase)

```
modified:   docs/ai-development-log.md
??  docs/design-decisions.md
??  docs/design-system.md
??  frontend/
```

Nothing was committed or pushed before, during, or after this phase — all
prior frontend work stayed exactly as the previous session left it. Baseline
`npm run build` (frontend, before any backend file existed) passed:

```
✓ 1629 modules transformed.
dist/index.html                 0.53 kB
dist/assets/index-*.css        53.56 kB
dist/assets/index-*.js        226-230 kB
✓ built in ~4s
```

## 2. Actual frontend Project/Task contract

Read directly from [`frontend/src/types/project.ts`](../frontend/src/types/project.ts) —
this is the real contract, not the illustrative shape in the integration brief:

```ts
interface Task {
  id: string
  name: string
  description: string
  assignee: string | null
  duration_workdays: number
  planned_effort_hours: number
  predecessor_ids: string[]
  successor_ids: string[]          // present on every task, derived
  start_not_before: string | null  // YYYY-MM-DD
  start_date: string                // YYYY-MM-DD
  end_date: string                  // YYYY-MM-DD
  display_order: number
  created_source: 'import' | 'agent'
}

interface Project {
  id: string
  name: string
  project_start_date: string       // YYYY-MM-DD
  revision: number
  tasks: Task[]
  created_at: string
  updated_at: string
}
```

This matches product-spec §6 field-for-field. **Conclusion: no schema
mismatch.** `app/schemas/project.py::ProjectOut`/`TaskOut` mirror it exactly,
including computing `successor_ids` at the API boundary (never stored on the
domain `Task` — see §6 below) so the response shape is correct without the
domain model pretending to own cross-task derived data.

## 3. Where the frontend already draws the mock/server boundary

`frontend/src/lib/diff.ts::computeChangeSet(before, after)` and
`frontend/src/fixtures/index.ts` are the only places fixture data enters the
app. `frontend/src/app/App.tsx` was the one file that actually decided which
`Project` object got rendered (`projectVersion: 'before' | 'after'` selecting
between two static fixture imports) — there was no real "data source"
concept yet, just two hardcoded snapshots. `frontend/src/features/chat/scenarios.ts`
classifies free-text chat input into one of 4 canned outcomes purely by
substring matching; it has no concept of a backend either.

**Decision:** introduce `dataSource: 'mock' | 'server'` as real `App.tsx`
state, set explicitly by successful actions (`server` on a real import or a
successful reload-restore, `mock` by every `DevStateSwitcher` entry and by
"Загрузить новый"), never inferred from a filename or a random id. `project`/
`changeSet` are derived from `dataSource`, not the other way around.

## 4. Differences found, and the adapter chosen for each

| # | What the prompt assumed | What the frontend actually has | Adapter decision |
|---|---|---|---|
| 1 | `frontend/src/api/client.ts` doesn't exist yet | Confirmed — no `api/` directory at all before this phase | Created `frontend/src/api/{client,projects}.ts` exactly as scoped; nothing else in `src/` reorganized |
| 2 | `Dropzone`'s `SelectedFile` carries enough info to upload | It only kept `{ name, size }` — the real browser `File` was discarded once read for display | Added one optional field, `raw?: File`. Its presence is the actual "is this a real pick" signal — not a filename heuristic — and it flows to `handleBuildPlan` unchanged |
| 3 | `ImportErrorScreen` can display arbitrary `{row, field, message}` issues | It only rendered its own internal `DEMO_IMPORT_ISSUES` constant, no props for real data | Added optional `message`, `issues`, `retryable` props, all defaulting to the exact previous demo behavior when omitted — the 12-state `DevStateSwitcher` entry is provably unaffected (covered by the mock-mode-unaffected check in Phase 2, see the spike report) |
| 4 | Chat can be "disabled" with a message in server mode | `ChatTurn` union only had `success/clarification/rejected/error` — no vocabulary for "not implemented yet" | Added a fifth kind, `'disabled'`, rendered with the exact same plain-bubble path as `'clarification'` — no new visual, only new data |
| 5 | A single `ProjectService.apply_change_set()` diff format would map 1:1 onto the frontend's `ChangeSet` type used by `ChangeSummary`/`GanttView` | The backend's natural diff shape (technical-blueprint §5-6: `direct_changes`/`created_tasks`/`dependency_changes`/`derived_schedule_changes`) and the frontend's `ChangeSet` (`byTask`, `modified`, `created`, `derived`, `previousSchedule`, `release`, …) are **not** the same shape — the frontend's is UI-presentation-oriented (grouped for the Gantt highlight index and the release-impact card), the backend's is a neutral audit diff | **Not built.** The dev `/changes` endpoint is deliberately never called by the frontend (chat stays on the mock `computeChangeSet` path or the "coming soon" placeholder — see integration brief's own instruction not to fake chat business logic). Building a `ChangeSet`-shaped adapter for an endpoint nothing renders would be speculative code for a diff format the next phase (MCP + real chat) will very likely reshape anyway. `docs/backend-architecture.md` §5 documents the two shapes side by side so the seam is visible when that phase starts |
| 6 | `planned_effort_hours` might need to be an editable field somewhere | Confirmed nowhere in the frontend treats it as anything but `duration_workdays × 8` for display | Backend never accepts it as input (`change_duration` operates in `workdays` or `person_hours`, never sets effort directly) — matches, no adapter needed |
| 7 | Export `Content-Disposition` filename would just work over `fetch()` | It didn't — browsers hide `Content-Disposition` from `fetch()` responses unless the server explicitly exposes it via CORS, which is easy to miss and was in fact missed on the first integration pass | Added `expose_headers=["Content-Disposition"]` to `CORSMiddleware` in `app/main.py`; caught by the Playwright integration check (`export download filename` assertion), not assumed to work |

## 5. A real bug the integration testing caught (not a contract mismatch, but worth recording)

`handleBuildPlan` starts the real `fetch` immediately but `ImportLoadingScreen`
holds the result for its full ~1.9s checklist animation before anything
`await`s it (by design — the animation must not depend on network timing).
A validation error from the backend can arrive in well under 1.9s, which
means nothing has attached a rejection handler to that promise yet — the
browser flags it as an unhandled promise rejection even though the eventual
`await` in `handleImportDone` does handle it correctly and the UI ends up
showing the right screen. Fixed by attaching a no-op `.catch()` the moment
the promise is created (`trackPending()` in `App.tsx`); the real error is
still observed later via the stored promise. Caught by the Playwright
integration run's console-error assertion, not by manual clicking.

## 6. Why `successor_ids` is not on the domain `Task`

Deliberate, not an oversight: `successor_ids` is cross-task derived data (it
depends on every task's `predecessor_ids`, not just its own). Keeping it off
`app/domain/models.py::Task` means nothing internal — the scheduler, the
change-set applier, the diff — can accidentally read or write it as if it
were authoritative per-task state. It is computed exactly once, at the
`app/schemas/project.py::project_to_out()` boundary, the same place
`planned_effort_hours` is computed via a `@computed_field` on the domain
`Task` itself (single-task, safe to keep close to the model).

## 7. Files touched to close the gap (minimal set)

Frontend (no redesign, no new dependency):

- `frontend/src/api/client.ts`, `frontend/src/api/projects.ts` — new
- `frontend/src/app/App.tsx` — data-source state, real import/export/restore wiring
- `frontend/src/app/types.ts` — no change (reused as-is)
- `frontend/src/components/Dropzone.tsx` — `+raw?: File`
- `frontend/src/features/import/ImportErrorScreen.tsx` — `+message`, `+issues`, `+retryable` (optional, backward compatible)
- `frontend/src/features/import/scenarios.ts` — `ImportIssue.row`/`.field` widened to allow `null`
- `frontend/src/features/chat/types.ts` — `+'disabled'` turn kind
- `frontend/src/features/chat/ChatPanel.tsx` — one added branch reusing the existing bubble
- `frontend/src/vite-env.d.ts` — `VITE_API_BASE_URL` typing
- `frontend/.env.example`, `frontend/public/` (unchanged — sample file already there)

Nothing in `frontend/src/styles/`, `frontend/src/components/{Button,Modal,Badge,...}`,
`frontend/src/features/gantt/`, `frontend/src/features/change-summary/`,
`frontend/src/features/task-modal/TaskDetailsModal.tsx`, or
`app/DevStateSwitcher.tsx` was touched.

Backend: everything under `backend/` is new (see `docs/backend-architecture.md`).

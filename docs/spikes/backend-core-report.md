# Spike Report — Backend Core + Frontend Integration

Python: **3.12.10** (installed this session via `winget install Python.Python.3.12`
— no interpreter existed on the machine beforehand; see the note in the final
chat response). Minimum supported per `backend/pyproject.toml`: 3.10.

All commands below were actually run; output is pasted verbatim (or the
tail of it, for long runs), not reconstructed from memory.

## 1. Criteria table

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Scheduler: single task starts on project start date | PASS | `test_scheduler.py::test_single_task_starts_on_project_start_date` |
| 2 | Scheduler: duration is inclusive of start day | PASS | `test_duration_is_inclusive_of_start_day` |
| 3 | Scheduler: Friday + 2 days lands on Monday | PASS | `test_friday_plus_two_days_lands_on_monday` |
| 4 | Scheduler: linear chain | PASS | `test_linear_chain` |
| 5 | Scheduler: parallel branches | PASS | `test_parallel_branches_run_independently` |
| 6 | Scheduler: multiple predecessors wait for the latest | PASS | `test_multiple_predecessors_wait_for_the_latest` |
| 7 | Scheduler: independent roots | PASS | `test_independent_roots_both_start_on_project_start` |
| 8 | Scheduler: start_not_before | PASS | `test_start_not_before_pushes_start_later_than_dependency_would_allow`, `test_start_not_before_does_not_override_a_later_dependency_start` |
| 9 | Scheduler: weekend project-start normalization + warning | PASS | `test_weekend_project_start_is_normalized_forward_with_warning` |
| 10 | Scheduler: weekend start_not_before normalization + warning | PASS | `test_weekend_start_not_before_is_normalized_forward_with_warning` |
| 11 | Scheduler: cycle detection | PASS | `test_cycle_is_detected_and_rejected` |
| 12 | Scheduler: deterministic order (display_order tie-break) | PASS | `test_deterministic_order_uses_display_order_as_tie_breaker` |
| 13 | Scheduler: exact canonical schedule vs. fixture | PASS | `test_exact_canonical_schedule_matches_fixture` — every date matches `fixtures/mock_project_before.json` by task name |
| 14 | Import: valid canonical sample | PASS | `test_import.py::test_valid_sample_imports_16_tasks`, `test_api.py::test_import_canonical_sample` |
| 15 | Import: first non-empty worksheet | PASS | `test_uses_first_non_empty_worksheet` |
| 16 | Import: normalized headers | PASS | `test_normalized_headers_with_surrounding_whitespace` |
| 17 | Import: missing column | PASS | `test_missing_column_is_rejected` |
| 18 | Import: duplicate normalized name (incl. ё/е) | PASS | `test_duplicate_normalized_name_is_rejected`, `test_yo_ye_are_treated_as_equivalent_duplicates` |
| 19 | Import: invalid/fractional duration | PASS | `test_invalid_duration_is_rejected[0,-1,2.5,abc,366]` |
| 20 | Import: duration accepts int-like float / numeric string | PASS | `test_duration_accepts_integer_like_float_and_numeric_string` |
| 21 | Import: unknown predecessor | PASS | `test_unknown_predecessor_is_rejected` |
| 22 | Import: forward predecessor reference | PASS | `test_forward_predecessor_reference_resolves` |
| 23 | Import: duplicate predecessor -> dedup + warning | PASS | `test_duplicate_predecessor_is_deduplicated_with_warning` |
| 24 | Import: self-dependency | PASS | `test_self_dependency_is_rejected` |
| 25 | Import: cycle | PASS | `test_cycle_is_rejected_at_import` |
| 26 | Import: formula detection (`data_only=False`) | PASS | `test_formula_in_required_field_is_rejected` |
| 27 | Import: optional "Не ранее" restored | PASS | `test_optional_start_not_before_column_is_restored` |
| 28 | Import: calculated columns ignored | PASS | `test_calculated_columns_are_ignored_not_source_of_truth` |
| 29 | Import: >500 tasks rejected | PASS | `test_more_than_max_tasks_is_rejected` |
| 30 | Import: oversized / bad workbook | PASS | `test_oversized_file_is_rejected`, `test_bad_workbook_bytes_are_rejected`, `test_non_xlsx_extension_is_rejected` |
| 31 | Import: filename never used as a filesystem path | PASS | `test_filename_is_never_used_as_a_filesystem_path` |
| 32 | ChangeSet: canonical multi-op success | PASS | `test_changeset.py::test_canonical_change_set_end_to_end`, `test_api.py::test_canonical_change_set_via_dev_endpoint` |
| 33 | ChangeSet: revision 1 -> 2, 16 -> 18 tasks | PASS | same as #32 |
| 34 | ChangeSet: release date = 2026-11-09 | PASS | same as #32 |
| 35 | ChangeSet: all-or-nothing rollback | PASS | `test_rollback_on_invalid_operation_leaves_revision_untouched` |
| 36 | ChangeSet: revision conflict under concurrent apply | PASS | `test_stale_revision_is_rejected_under_concurrent_apply` (real `asyncio.gather`, not sequential) |
| 37 | ChangeSet: duplicate / unresolved / forward client_ref | PASS | `test_duplicate_client_ref_is_rejected`, `test_unresolved_client_ref_is_rejected`, `test_forward_client_ref_within_same_change_set_resolves` |
| 38 | ChangeSet: cycle introduced by a change set | PASS | `test_cycle_introduced_by_change_set_is_rejected` |
| 39 | ChangeSet: rename to duplicate name | PASS | `test_rename_to_duplicate_name_is_rejected` |
| 40 | ChangeSet: 24h -> 3 days, +16h -> +2 days, 12h rejected | PASS | `test_change_duration_set_person_hours_24_equals_3_days`, `test_change_duration_add_16_hours_adds_2_days`, `test_change_duration_12_hours_rejected_no_silent_rounding` |
| 41 | ChangeSet: subtract below minimum rejected | PASS | `test_subtract_below_minimum_is_rejected` |
| 42 | ChangeSet: move earlier violating dependency rejected | PASS | `test_move_task_earlier_violating_dependency_is_rejected` |
| 43 | ChangeSet: clear_start_constraint | PASS | `test_clear_start_constraint_lets_scheduler_pick_earliest` |
| 44 | ChangeSet: parallel create + QA set_predecessors (canonical) | PASS | part of #32 |
| 45 | ChangeSet: insert_task_between requires direct edge | PASS | `test_insert_task_between_requires_direct_edge`, `test_insert_task_between_rewires_edge_atomically` |
| 46 | ChangeSet: deterministic display_order + diff | PASS | `test_deterministic_display_order_after_creates` |
| 47 | Export: canonical 18 tasks, predecessor names, dates, effort, metadata | PASS | `test_export.py` (7 tests) |
| 48 | Export: formula-injection protection | PASS | `test_formula_injection_is_neutralized` |
| 49 | Export: round-trip | PASS | `test_export_canonical_18_tasks_round_trips`, plus a full HTTP round-trip in `canonical_verify.py` (§3 below) |
| 50 | API: health independent of store | PASS | `test_health_does_not_require_store` |
| 51 | API: import / get / missing project (404 + error shape) | PASS | `test_import_canonical_sample`, `test_get_project_after_import`, `test_get_missing_project_returns_404_with_error_shape` |
| 52 | API: dev endpoint disabled by default, enabled in test config | PASS | `test_dev_endpoint_registered_when_enabled`, `test_dev_endpoint_not_registered_when_disabled` |
| 53 | API: canonical change set via HTTP | PASS | `test_canonical_change_set_via_dev_endpoint` |
| 54 | API: revision conflict -> 409 | PASS | `test_revision_conflict_returns_409` |
| 55 | API: export headers + file validity | PASS | `test_export_returns_xlsx_with_content_disposition` |
| 56 | Store: two projects isolated | PASS | `test_store.py::test_two_projects_are_isolated` |
| 57 | Store: concurrent stale revision cannot both commit | PASS | `test_apply_checks_revision_inside_the_lock` (+ #36 at the service layer) |
| 58 | Frontend: `npm run build` passes after integration | PASS | §4 below |
| 59 | Frontend: no dead generated `.js`/`.d.ts` in `src/` | PASS (after cleanup) | Found ~140 stray files from an earlier malformed `tsc -b --noEmit false` run in the *previous* session; deleted (`find src -name "*.js" -o -name "*.d.ts" | grep -v vite-env`) — verified empty before final build |
| 60 | Frontend integration: server import success, structured error, backend unavailable, date-only rendering, reload restore, real export, no console errors | PASS | §5 below (Playwright, real browser, real backend) |
| 61 | Frontend integration: 1440/1280/1024 smoke, Gantt scroll doesn't move Chat | PASS | §5 below |

**61/61 criteria checked, all PASS.** No criterion was skipped, and none was
marked PASS without the command/test that proves it (see §2-§5 for exact
commands and raw output).

## 2. Backend test run

```
cd backend
./.venv/Scripts/python.exe -m pytest -v
```

```
collected 79 items
...
============================= 79 passed in 5.63s ==============================
```

Breakdown by file: `test_api.py` (11), `test_changeset.py` (17), `test_export.py`
(7), `test_import.py` (21), `test_scheduler.py` (14), `test_store.py` (4) = 79.

## 3. Canonical verification against a real running server

```
cd backend
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then, from a separate script hitting real HTTP (`httpx`), against
`examples/sample_patient_card_project.xlsx` and `project_start_date=2026-09-07`:

```
== GET /health ==
200 {'status': 'ok'}

== POST /projects/import (canonical sample) ==
201
task count: 16 expect 16
revision: 1 expect 1
release date: 2026-11-02 expect 2026-11-02

== GET /projects/{id} ==
OK, matches imported project id

== POST /projects/{id}/changes (canonical ChangeSet, dev endpoint) ==
200
task count: 18 expect 18
revision: 2 expect 2
release date: 2026-11-09 expect 2026-11-09
agreement duration/effort: 5 40 expect 5 40
frontend duration/effort: 8 64 expect 8 64
created_tasks: ['Правки backend по итогам согласования', 'Правки frontend по итогам согласования']
direct_changes count: 3
derived_schedule_changes count: 12

== GET /projects/{id}/export ==
200 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
attachment; filename*=UTF-8''sample_patient_card_project.xlsx; filename="sample_patient_card_project.xlsx"
export size: 7440 bytes

== round-trip: open exported workbook with openpyxl, re-import it ==
sheets: ['План', 'Метаданные']
plan rows (incl header): 19 expect 19
metadata: {'project_name': 'sample_patient_card_project', 'project_start_date': '2026-09-07', 'revision': 2, 'exported_at_utc': '2026-08-23T19:47:56.174671+00:00'}
re-imported task count: 18 expect 18
re-imported dependencies/assignees preserved correctly

ALL CANONICAL VERIFICATION CHECKS PASSED
```

This is the exact scenario from product-spec §18, run against a live HTTP
server, not asserted from unit tests alone.

## 4. Frontend build

```
cd frontend
npm run build
```

```
> tsc -b && vite build
✓ 1631 modules transformed.
dist/index.html                 0.53 kB │ gzip:  0.33 kB
dist/assets/index-*.css        53.56 kB │ gzip:  9.33 kB
dist/assets/index-*.js        230.56 kB │ gzip: 70.82 kB
✓ built in 3.72s
```

## 5. Frontend integration verification (Playwright, headless Chrome, real backend + real dev server)

Script drove: real dropzone upload of `examples/sample_patient_card_project.xlsx`
→ real `POST /import` → Workspace with 16 real tasks → real Task Details Modal
→ chat send in server mode → real `GET /export` with a real browser download →
page reload → session-restored Workspace via `GET /projects/{id}` → a second
run with a genuinely invalid `.xlsx` (bad duration, unknown predecessor) →
Import Error screen showing the actual backend-returned row/field/message →
a third run with all `/api/v1/**` requests aborted (backend-unavailable
simulation) → the network-error message → `DevStateSwitcher` mock states
re-verified unaffected → 1440/1280/1024px smoke.

```
has "16 задач": true
has "2 ноября" (release, unchanged): true
legend present in server mode (expect 0): 0
export download filename: sample_patient_card_project.xlsx
[real-import-flow] console errors: (none)
restored after reload, still shows 16 tasks: true
[reload-restore] console errors: (none)
shows real backend issue text (duration): true
[structured-import-error] console errors: Failed to load resource: the server responded with a status of 422 (Unprocessable Entity)
shows network-unavailable message: true
mock legend present (expect true): true
mock release change shown: true
[mock-mode-unaffected] console errors: (none)
responsive width=1440: overflow=false errors=0
responsive width=1280: overflow=false errors=0
responsive width=1024: overflow=false errors=0

DONE
```

The one remaining "console error" line is the browser's own standard log
entry for a non-2xx `fetch()` response (Chrome logs this for *any* failed
request regardless of whether the application handles it) — it is not a
`pageerror`/uncaught exception, and the app's own handling (the correct
Import Error screen, with the real backend message) is confirmed working in
the same run. An actual bug this same check *did* catch and get fixed
(unhandled promise rejection from an import request settling before it was
awaited) is documented in `docs/backend-contract-audit.md` §5.

## 6. What's still mock

- Chat business logic (`features/chat/scenarios.ts`) — mock mode only; server
  mode shows a fixed "coming soon" message per turn, never calls the backend.
- The dev `/changes` endpoint is exercised only by pytest and the canonical
  `httpx` script above — no UI path calls it.
- `Дата начала проекта` on the Import screen is real input now (sent to the
  backend), but the backend's own weekend-normalization warning is not
  surfaced anywhere in the UI yet (it's in the API response's `warnings`
  array, unread by the frontend) — the visual states didn't ask for a
  warnings banner, so none was added speculatively.

"""AmbiguityGuard — a small, deterministic server-side check that stops a
mutation from silently resolving a name ambiguity the model should have
asked about instead.

Why this exists: the system prompt already tells the model to ask instead of
guessing when a task reference matches several plausible candidates, but a
model is free to ignore prompt-level instructions. This guard makes the
"ask, don't guess" rule mechanically enforced (like the one-mutation-per-turn
rule already is in `AgentService._run_loop`) rather than merely requested.

Policy (deterministic, no NLP classifier):

1. Only engages when the most recent `search_tasks` call in this turn
   returned 2+ results — that is the "several plausible candidates" signal.
2. Only engages when the pending `apply_change_set` actually references one
   of those candidates' task ids somewhere in its operations.
3. Is bypassed by an explicit multi-target signal in the *current* user
   message: a marker word ("обе", "все", "каждую", ...), or the user naming
   enough of each candidate's distinguishing words (e.g. "backend" and
   "frontend") to make it clear more than one task is intentionally in
   scope.
4. Otherwise: block. The caller (AgentService) must not call the mutation
   tool at all and should return `clarification_required` naming the
   candidates instead.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

_MULTI_TARGET_MARKERS = frozenset(
    {
        "обе",
        "обеих",
        "оба",
        "обоих",
        "все",
        "всех",
        "каждую",
        "каждой",
        "каждый",
        "каждого",
        "любые",
    }
)


@dataclass(frozen=True)
class SearchCandidate:
    id: str
    name: str


@dataclass(frozen=True)
class AmbiguityVerdict:
    blocked: bool
    candidates: list[SearchCandidate] = field(default_factory=list)


def _tokenize(text: str) -> set[str]:
    return {tok.lower() for tok in _TOKEN_RE.findall(text or "")}


def _distinguishing_tokens(candidates: list[SearchCandidate]) -> dict[str, set[str]]:
    """For each candidate, the tokens in its name that no other candidate's
    name also has — e.g. for "Backend-разработка..." vs
    "Frontend-разработка...", that is just {"backend"} / {"frontend"}."""
    token_sets = {c.id: _tokenize(c.name) for c in candidates}
    result: dict[str, set[str]] = {}
    for cid, tokens in token_sets.items():
        others: set[str] = set()
        for other_id, other_tokens in token_sets.items():
            if other_id != cid:
                others |= other_tokens
        result[cid] = tokens - others
    return result


def _extract_task_id_references(raw_arguments_json: str) -> set[str]:
    """Walk the (untrusted) apply_change_set arguments JSON for every
    `task_id` value, wherever it appears (a mutation target, a predecessor
    ref, a display_after_ref, ...). Deliberately shape-agnostic instead of
    hard-coding each operation type's fields — that keeps this guard from
    having to be updated every time an operation gains a new task_id-bearing
    field."""
    try:
        parsed: Any = json.loads(raw_arguments_json) if raw_arguments_json else {}
    except (TypeError, ValueError):
        return set()

    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("task_id")
            if isinstance(value, str):
                found.add(value)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(parsed)
    return found


def evaluate_ambiguity(
    *,
    user_message: str,
    search_candidates: list[SearchCandidate] | None,
    raw_apply_arguments_json: str,
) -> AmbiguityVerdict:
    if not search_candidates or len(search_candidates) < 2:
        return AmbiguityVerdict(blocked=False)

    ambiguous_ids = {c.id for c in search_candidates}
    referenced_ids = _extract_task_id_references(raw_apply_arguments_json)
    touched = referenced_ids & ambiguous_ids
    if not touched:
        return AmbiguityVerdict(blocked=False)

    message_tokens = _tokenize(user_message)
    if message_tokens & _MULTI_TARGET_MARKERS:
        return AmbiguityVerdict(blocked=False)

    distinguishing = _distinguishing_tokens(search_candidates)
    explicitly_named_ids = {
        cid for cid, tokens in distinguishing.items() if tokens and tokens <= message_tokens
    }
    if touched <= explicitly_named_ids:
        return AmbiguityVerdict(blocked=False)

    return AmbiguityVerdict(blocked=True, candidates=list(search_candidates))

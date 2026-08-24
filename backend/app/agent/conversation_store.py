"""Per-project chat history, visible messages only — no chain-of-thought, no
raw tool traces. In-memory, lost on restart (same MVP debt as
InMemoryProjectStore — see docs/backend-architecture.md).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ConversationTurn:
    role: Literal["user", "assistant"]
    content: str


class InMemoryAgentConversationStore:
    def __init__(self, *, max_turns: int) -> None:
        self._max_turns = max_turns
        self._by_project: dict[uuid.UUID, list[ConversationTurn]] = {}

    def get_history(self, project_id: uuid.UUID) -> list[ConversationTurn]:
        return list(self._by_project.get(project_id, []))

    def append_turn(self, project_id: uuid.UUID, *, user_message: str, assistant_message: str) -> None:
        history = self._by_project.setdefault(project_id, [])
        history.append(ConversationTurn(role="user", content=user_message))
        history.append(ConversationTurn(role="assistant", content=assistant_message))
        limit = self._max_turns * 2  # user+assistant pair per turn
        if len(history) > limit:
            del history[: len(history) - limit]

    def clear(self, project_id: uuid.UUID) -> None:
        self._by_project.pop(project_id, None)

# AI Gantt Planner — Technical Blueprint Draft

**Статус:** draft до завершения technical spikes  
**Назначение:** зафиксировать предварительную архитектуру и решения для проверки

## 1. Цель этапа

До полноценной разработки проверить два главных технических риска:

1. подходит ли выбранная React Gantt-библиотека;
2. работает ли цепочка OpenRouter → MCP → backend domain layer.

После spikes документ должен быть обновлён до `technical-blueprint.md`.

## 2. Предварительный стек

| Область | Решение |
|---|---|
| Frontend | React + TypeScript + Vite |
| Gantt | `@svar-ui/react-gantt` как первый кандидат |
| Server state | TanStack Query |
| Local UI state | React state / useReducer |
| Backend | Python + FastAPI + Pydantic |
| Excel | openpyxl |
| Scheduler | собственный детерминированный модуль |
| Project Store | In-memory repository |
| MCP | официальный Python SDK |
| LLM | OpenRouter |
| Production | один Docker-сервис |
| Hosting | Render как первый вариант |

## 3. Архитектурный принцип

```text
React
↓ REST
FastAPI
↓
Agent Orchestrator
↓
OpenRouter
↓ tool call
MCP Client
↓
MCP Server
↓
Project Service
↓
Validation + Scheduler
↓
Project Store
```

Ключевое правило:

> Agent Orchestrator не должен напрямую вызывать mutation ProjectService в обход MCP.

## 4. Frontend

Frontend не рассчитывает:

- даты;
- рабочие дни;
- successors;
- релиз;
- person-hours как независимое состояние.

Source of truth:

```text
Project DTO от backend
```

После успешной AI-команды frontend заменяет project state серверным DTO.

### Предварительная структура

```text
frontend/
└── src/
    ├── api/
    ├── app/
    ├── components/
    ├── features/
    │   ├── import/
    │   ├── gantt/
    │   ├── chat/
    │   └── task-modal/
    └── types/
```

## 5. Gantt adapter

Backend DTO не должен передаваться библиотеке напрямую.

```text
Project DTO
↓
mapProjectToGanttData()
↓
Gantt tasks + links
```

Пример:

```ts
interface GanttTask {
  id: string;
  text: string;
  start: Date;
  end: Date;
  duration: number;
  type: "task";
  assignee: string | null;
  plannedEffortHours: number;
  changeType?: "direct" | "created" | "derived";
}

interface GanttLink {
  id: string;
  source: string;
  target: string;
  type: "e2s";
}
```

## 6. Change highlighting

Приоритет:

```text
created > direct > derived
```

Frontend строит индекс изменений из:

```text
direct_changes
created_tasks
dependency_changes
derived_schedule_changes
```

Различия не должны строиться только на цвете.

## 7. Backend structure

Предварительно:

```text
backend/app/
├── api/
├── domain/
├── scheduler/
├── services/
├── storage/
├── mcp/
├── agent/
├── schemas/
├── settings.py
└── main.py
```

### Ответственность

`api/`:
- HTTP transport;
- без бизнес-логики.

`domain/`:
- Project;
- Task;
- ChangeSet;
- operations;
- errors;
- constants.

`scheduler/`:
- граф;
- workdays;
- topological sort;
- date calculation.

`services/`:
- ProjectService;
- import/export.

`storage/`:
- repository abstraction;
- in-memory implementation.

`mcp/`:
- MCP Server;
- MCP Client;
- tools;
- schemas.

`agent/`:
- OpenRouter client;
- orchestrator;
- prompts;
- tool conversion.

## 8. Scheduler

Детерминированный и независимый от LLM.

Правила:

- Mon–Fri;
- Finish-to-Start;
- multiple predecessors;
- cycle detection;
- one workday = 8 person-hours;
- full recalculation допустим до 500 задач.

## 9. MCP

Read tools:

```text
get_project_outline
get_task_details
search_tasks
```

Mutation:

```text
apply_change_set
```

MCP tool вызывает ProjectService.

Agent Orchestrator вызывает MCP Client.

Запрещено:

```text
Agent → ProjectService mutation directly
```

## 10. OpenRouter

Environment:

```text
OPENROUTER_API_KEY
OPENROUTER_MODEL
```

Модель выбирается через env и должна поддерживать tool calling.

Ограничения agent loop:

```text
max_iterations = 6
max_mutation_calls = 1
temperature ≈ 0.1
```

## 11. REST API

```text
POST /api/v1/projects/import
GET  /api/v1/projects/{project_id}
POST /api/v1/projects/{project_id}/chat
GET  /api/v1/projects/{project_id}/export
GET  /api/v1/health
```

## 12. Deployment

Предварительное решение:

```text
React build
↓
FastAPI StaticFiles
+
REST API
+
MCP Server
+
Agent Orchestrator
```

Один Docker container на Render.

Плюсы:

- одна публичная ссылка;
- проще CORS;
- проще env;
- проще demo;
- in-memory state не разделяется между разными backend services.

## 13. Spike A — Gantt

Вход:

```text
fixtures/mock_project_before.json
fixtures/mock_project_after.json
```

Проверить:

- 16 задач до;
- 18 после;
- UUID;
- dependency arrows;
- read-only;
- modal;
- horizontal/vertical scroll;
- dynamic DTO replacement;
- direct/created/derived highlighting;
- 500-task performance;
- отсутствие зависимости от PRO-only функций.

Результат:

```text
docs/spikes/gantt-spike-report.md
```

## 14. Spike B — Domain logic

Без LLM, MCP, Excel и frontend.

Проверить:

- Project/Task/ChangeSet models;
- InMemoryProjectStore;
- Scheduler;
- atomic apply_change_set;
- revision;
- client_ref;
- rollback;
- canonical result совпадает с `mock_project_after.json`.

Результат:

```text
docs/spikes/domain-spike-report.md
```

## 15. Spike C — MCP

Поверх работающего ProjectService.

Проверить:

- реальный MCP Server;
- MCP Client;
- tool schemas;
- tool invocation through MCP;
- canonical change set через MCP.

Результат:

```text
docs/spikes/mcp-spike-report.md
```

## 16. Spike D — OpenRouter

Проверить:

- smoke request;
- simple tool calling;
- canonical command;
- не более одного mutation;
- 5/5 семантически корректных прогонов после стабилизации.

## 17. Observability

Логировать:

```text
request_id
project_id
conversation_id
model
iteration_number
tool_name
tool_status
previous_revision
new_revision
latency_ms
```

Не логировать:

- API key;
- hidden chain-of-thought;
- `.env`;
- чувствительные данные.

## 18. Решения, которые ещё должны быть подтверждены spikes

- финальная Gantt library;
- версия MCP SDK;
- MCP transport;
- конкретная OpenRouter model;
- frontend component details;
- deployment host;
- browser performance на 500 задачах.

После проверки этот документ должен стать `docs/technical-blueprint.md`.

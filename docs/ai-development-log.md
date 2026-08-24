# AI Development Log

В этом документе фиксируется использование AI-ассистентов при разработке AI Gantt Planner.

Цель журнала — показать не только факт использования AI, но и управляемый процесс: какие задачи делегировались ассистентам, какие решения были проверены вручную, какие ошибки были обнаружены и какие решения приняты человеком.

---

## Запись 1 — Product & System Specification

### Этап

Product discovery / бизнес- и системный анализ.

### Задача

Сформировать требования к AI Gantt Planner перед началом разработки.

### Использованный AI-инструмент

ChatGPT.

### Переданный контекст

- обязательный стек;
- формат входного Excel;
- требования тестового задания;
- сценарий интерактивного Гантта и AI-чата;
- реальный продуктовый сценарий — разработка карточки пациента для платформы стоматологов.

### Что предложил AI

- разделить систему на Project Domain Model, Scheduler, AI Agent, MCP tools, Frontend и Excel I/O;
- не использовать LLM как source of truth;
- применять изменения атомарными change sets;
- ввести revision control;
- использовать реальный рабочий сценарий вместо абстрактного demo.

### Что было проверено вручную

- соответствие обязательному стеку;
- логика бизнес-процесса;
- последовательность discovery → согласование → дизайн → разработка → QA → релиз;
- реалистичность demo-сценария.

### Обнаруженные проблемы

В ранней версии требований были недоопределены:

- семантика переноса задач;
- идентификация predecessors;
- атомарность нескольких AI-операций;
- использование MCP;
- пересчёт расписания;
- различие длительности и трудоёмкости;
- несколько исполнителей на одном этапе.

### Принятое решение

- один Task имеет одного assignee;
- если работают два разработчика — создаются две параллельные задачи;
- `1 рабочий день = 8 плановых человеко-часов`;
- LLM формирует операции, backend валидирует и применяет их;
- один пользовательский запрос = один atomic change set;
- новые задачи внутри change set связываются через `client_ref`.

### Результат

Подготовлена спецификация `docs/product-spec.md` версии 0.3.

---

## Запись 2 — Demo Dataset

### Этап

Подготовка тестовых данных.

### Задача

Создать реалистичный тестовый проект для frontend, backend, AI и demo.

### Использованный AI-инструмент

ChatGPT.

### Переданный контекст

Реальный кейс разработки карточки пациента для стоматологической платформы.

### Что предложил AI

Подготовить:

- sample Excel;
- Project DTO до AI-команды;
- Project DTO после AI-команды.

### Что было проверено вручную

- роли команды;
- порядок этапов;
- наличие бизнес-согласований;
- параллельность frontend/backend;
- отдельные задачи для Анны П и Анны С.

### Принятое решение

Каноническая команда одновременно:

- увеличивает длительность согласования требований;
- увеличивает frontend;
- создаёт backend/frontend правки;
- меняет dependencies QA;
- демонстрирует каскадный пересчёт релиза.

### Результат

Созданы:

```text
examples/sample_patient_card_project.xlsx
fixtures/mock_project_before.json
fixtures/mock_project_after.json
```

---

## Запись 3 — High-Fidelity UX/UI Design

### Этап

Product design / UI design / design engineering — визуальный прототип frontend.

### Задача

Спроектировать и реализовать high-fidelity frontend-прототип AI Gantt Planner (React + TypeScript + Vite, без backend/AI-интеграции) на основе `docs/product-spec.md`, `fixtures/mock_project_before.json` и `fixtures/mock_project_after.json`, демонстрирующий связку Gantt + AI Chat + Change Summary + Release impact на каноническом сценарии карточки пациента.

### Использованный AI-инструмент

Claude Code (Claude Sonnet 5).

### Переданный контекст

- полный текст `docs/product-spec.md` v0.3 (доменная модель, правила Scheduler, change-семантика direct/created/derived, каноническая AI-команда и её ожидаемый результат);
- `fixtures/mock_project_before.json` / `mock_project_after.json` — единственный источник данных для demo;
- уже существующая, но не законченная работа предыдущей сессии: design tokens (`styles/tokens.css`), базовые UI-примитивы (`components/*`), fixture adapter, `lib/date.ts`, `lib/diff.ts` (вычисление ChangeSet из двух ревизий проекта), а также каркас Gantt-модели (`features/gantt/ganttModel.ts`, `ganttGeometry.ts`) и готовый CSS-модуль `GanttView.module.css` без самого React-компонента;
- явные визуальные и продуктовые ограничения: light theme, без AI-градиентов/glow/glassmorphism, high information density, Gantt важнее Chat, запрет на функциональность вне MVP (status, priority, drag-and-drop, dark mode и т.д.).

### Промпт

Полный расширенный промпт пользователя с ролью «Senior Product Designer + Senior UI/UX Designer + Design Engineer» — детальная спецификация всех экранов и состояний (Import/Loading/Error, Workspace, AI Chat во всех исходах, Task Modal, Upload Confirmation, Export), design tokens, reusable-компонентов и требований к финальной проверке (build, responsive, console errors). Задача явно указана как продолжение прерванной работы: «изучи промпт, весь репозиторий и выполненную работу» перед стартом.

### Что предложил AI

- достроить прототип поверх уже готового фундамента, а не переписывать его — сохранить существующие design tokens, `lib/diff.ts`/`lib/date.ts` и модель Gantt как есть;
- реализовать состояние приложения как явный набор атомарных React state-переменных в `App.tsx` (`screen`, `projectVersion: 'before'|'after'`, `chatTurns`, `chatStatus`, `selectedTaskId`, `exportStatus`, `uploadConfirmOpen`) и единый `applyDevState()` для dev-переключателя, вместо конечного автомата на классах/машине состояний — проще для 12 требуемых состояний и для будущей замены на реальные API-вызовы;
- классифицировать свободный текст в AI-чате простой эвристикой (`features/chat/scenarios.ts`: подстроки «api», «qa»+«перенос/дату», «недоступ») поверх единственного реального перехода `before → after` — так все обязательные состояния (clarification/rejected/technical error) достижимы через реальный ввод, а не только через dev-переключатель;
- визуально отделить весь dev-инструментарий (`DevStateSwitcher`, demo-хелпер с канонической командой) от продуктового UI через тёмную/dashed/monospace стилистику, не пересекающуюся с токенами продукта;
- вынести Release impact как самостоятельный, визуально самый громкий блок — и в метриках над Gantt, и в `ChangeSummary` в чате.

### Что было проверено вручную

- построчное сравнение реализованного Gantt/ChangeSummary с ожидаемым результатом канонической команды из §18 product-spec (3→5 дней согласования, 7→8 дней frontend, 2 новые параллельные задачи, пересчёт QA и релиза на 09.11.2026) — воспроизведено через `computeChangeSet(before, after)`, без хардкода итоговых чисел;
- ручной прогон всех 12 обязательных UI-состояний через dev-переключатель и через реальные интеракции (drag&drop файла, отправка сообщений, эскиз-триггеры clarification/rejected/error) в headless Chrome (Playwright) — сняты скриншоты, проверена консоль на ошибки;
- `npm run build` (tsc -b + vite build) — до правок обнаружены и исправлены 5 ошибок типов, не связанных с новым кодом (пре-существующий баг в `cx()`-вызовах трёх компонентов, отсутствовавший `@types/node` для `vite.config.ts`);
- проверка layout на 1440/1280/1024px — `document.documentElement.scrollWidth` не превышает `clientWidth` ни на одной ширине, горизонтальный скролл Gantt не затрагивает колонку чата;
- обнаружены и удалены posторонние скомпилированные `.js`/`.d.ts` файлы, случайно оказавшиеся внутри `src/` после первого (неудачного) прогона `tsc -b` с несовместимыми флагами.

### Обнаруженные проблемы

- в `Input`/`Textarea`/`DateInput` выражение `error && styles.invalid` не проходило строгую типизацию `cx()` (`error: ReactNode` допускает `0`) — исправлено на `Boolean(error) && …`;
- `vite.config.ts` не типизировался без `@types/node` (отсутствовал в `devDependencies`) — добавлен;
- в модалке задачи не хватало отступа между описанием и первой секцией метаданных — добавлен `margin-bottom` у параграфа описания;
- demo-хелпер с канонической командой в чате визуально «слипался» с кнопкой на узкой колонке чата — переверстан в две строки;
- отсутствовал favicon → лишний 404 в консоли при каждой загрузке — добавлен `favicon.svg` с логотипом продукта.

### Какое решение принято

- продолжать и достраивать существующий фундамент предыдущей сессии, не переписывая его с нуля;
- все обязательные 12 UI-состояний реализованы как достижимые двумя путями одновременно: обычным взаимодействием пользователя **и** одним кликом в dev-переключателе — для интерактивного ревью и для быстрой проверки без повторения сценария вручную;
- пример Excel (`examples/sample_patient_card_project.xlsx`) скопирован статическим ассетом в `frontend/public/`, чтобы ссылка «Скачать пример Excel» была реальной загрузкой файла, а не декоративной — это не противоречит запрету на реализацию Excel import/export логики, так как файл не парсится и не генерируется фронтендом.

### Результат

Реализован полный high-fidelity прототип: `frontend/src/app/*` (App, Workspace, Header, ProjectMetricsBar, DevStateSwitcher, UploadConfirmDialog), `frontend/src/features/{import,gantt,chat,change-summary,task-modal}/*`, `docs/design-system.md`, `docs/design-decisions.md`. `npm run build` проходит без ошибок, все 12 UI-состояний проверены визуально и на отсутствие console errors на 1440/1280/1024px.

### Что требует человеческой проверки

- реальный dependency-парсинг и cycle-detection при подключении Scheduler — фронтенд сейчас доверяет датам из DTO как есть;
- поведение `ChatPanel` на очень длинной истории сообщений (сейчас проверено на 1–2 turns, реальный backend может вернуть намного больше);
- доступность (screen reader) диаграммы Gantt — сейчас есть базовые `aria-label`/`role`, но полноценный keyboard-навигационный обход баров и стрелок зависимостей не реализован;
- итоговые copy-тексты стоит сверить с продакт-командой перед реальным релизом — часть формулировок (ошибки импорта, clarification) — иллюстративные примеры в духе спецификации, а не финальные тексты.

---

## Запись 4 — Backend Core + Frontend API Integration

### Этап

Backend engineering / system architecture / integration.

### Задача

Реализовать детерминированный backend (Excel import, Scheduler, ChangeSet operations, Excel export) на Python/FastAPI/Pydantic v2/openpyxl и минимально интегрировать его с уже готовым frontend-прототипом для реального импорта, получения Project DTO, восстановления проекта после reload и Excel export — без OpenRouter, LLM и MCP на этом этапе.

### Использованный AI-инструмент

Claude Code (Claude Sonnet 5).

### Переданный контекст

- полный текст `docs/product-spec.md`, `docs/technical-blueprint-draft.md`, `docs/design-system.md`, `docs/design-decisions.md`;
- фактическая структура уже реализованного frontend (`frontend/src/app`, `features/{import,gantt,chat,change-summary,task-modal}`, `lib/diff.ts`, `types/project.ts`) — явное требование промпта: не опираться на предполагаемые пути, а прочитать реальный код;
- жёсткое разделение источников истины: product-spec — для бизнес-правил, существующий frontend — для UX/визуального поведения, backend после импорта — единственный источник истины для Project state и рассчитанных дат;
- явный запрет менять product-spec, fixtures, examples, design tokens, Gantt geometry, plotность 32px/строка и DevStateSwitcher без блокирующей причины.

### Промпт

Детальный промпт с ролью «Senior Python Backend Engineer, System Architect и Integration Engineer»: Phase 0 аудит перед изменениями, доменная модель и константы, нормализация имён (ё/е, whitespace), полностью независимый детерминированный Scheduler, InMemoryProjectStore с per-project asyncio.Lock и revision-check внутри лока, ExcelImportService и ExcelExportService с конкретными правилами валидации и защитой от formula injection, 10 ChangeSet-операций с client_ref механикой, REST API с единым форматом ошибок и dev-only `/changes` endpoint (по умолчанию выключен), требования к frontend-интеграции через отдельный `frontend/src/api/*` слой без новых тяжёлых зависимостей, требование реально запустить backend и пройти канонический сценарий, а не только написать тесты, и не заявлять «готово» без фактического вывода pytest/build.

### Что предложил AI

- перед началом — Phase 0 аудит: прочитать `frontend/src/types/project.ts` как источник фактического контракта (а не полагаться на иллюстративные шейпы из промпта), задокументировать найденные расхождения и решить их точечными адаптерами, а не редизайном (см. `docs/backend-contract-audit.md`);
- реализовать diff двух способов независимо: backend строит `ChangeSummary` (`direct_changes`/`created_tasks`/`dependency_changes`/`derived_schedule_changes`) по снэпшотам before/after — той же стратегией, что уже использует `frontend/src/lib/diff.ts` для mock-демо, но не пытаться свести два разных по назначению diff-шейпа (backend-аудит vs UI-презентация) в один адаптер без реальной необходимости — задокументировать разрыв явно вместо спекулятивного кода;
- ввести явное состояние `dataSource: 'mock' | 'server'` во frontend, устанавливаемое только результатом конкретных действий (успешный реальный импорт, восстановление после reload, dev-переключатель, «Загрузить новый»), никогда не по имени файла или случайному id;
- добавить одно опциональное поле `raw?: File` в существующий `SelectedFile`, чтобы отличать реальный выбор файла от decorативного mock-состояния — вместо эвристики по имени;
- переиспользовать существующий `ImportErrorScreen`/`ChatPanel`/`Header` без визуальных изменений, расширив только props (`message`/`issues`/`retryable`, новый `ChatTurn.kind: 'disabled'`) с дефолтами, полностью совпадающими с прежним mock-поведением.

### Что было проверено вручную

- перед началом обнаружено, что на машине не установлен ни один реальный Python-интерпретатор (только заглушка Windows Store) — задача была явно заблокирована требованием промпта «не утверждай PASS без фактического запуска»; пользователь подтвердил установку Python 3.12 через `winget`, после чего работа продолжилась;
- полный прогон `pytest` backend (79 тестов: scheduler, import, export, changeset, API, store) — все проходят, вывод сохранён в `docs/spikes/backend-core-report.md`;
- канонический сценарий прогнан через реально запущенный HTTP-сервер (`uvicorn`), а не только через unit-тесты: импорт `examples/sample_patient_card_project.xlsx` → 16 задач, revision 1, релиз 02.11.2026; каноническая ChangeSet-команда → 18 задач, revision 2, релиз 09.11.2026; export → round-trip через openpyxl подтверждает сохранность всех полей;
- полная интеграция проверена через headless Chrome (Playwright) против реально запущенных backend + frontend одновременно: реальный drag-and-drop импорт через UI, открытие Task Modal с реальными данными, chat в server mode («AI-редактирование будет подключено на следующем этапе»), реальный export с реальной загрузкой файла браузером, reload → восстановление проекта через `sessionStorage` + `GET /projects/{id}`, реальная structured Import Error через фактически невалидный `.xlsx`, симуляция недоступности backend (перехват всех `/api/v1/**` запросов), проверка, что mock DevStateSwitcher не пострадал, и responsive-smoke на 1440/1280/1024px;
- `npm run build` (frontend) и `pytest` (backend) прогнаны после каждого содержательного изменения, а не один раз в конце.

### Обнаруженные проблемы

- на первом прогоне интеграции CORS блокировал реальный импорт (порт frontend dev-сервера не совпадал с `FRONTEND_ORIGINS` в `backend/.env`) — исправлено расширением allow-list и синхронизацией портов;
- браузер по умолчанию скрывает заголовок `Content-Disposition` от `fetch()` при cross-origin запросах, если сервер явно не открыл его через CORS — из-за этого реальное имя экспортированного файла терялось на фронтенде (falling back на `project.xlsx`); исправлено добавлением `expose_headers=["Content-Disposition"]` в `CORSMiddleware`;
- обнаружен unhandled promise rejection: `handleBuildPlan` запускает реальный `fetch` немедленно, но `ImportLoadingScreen` намеренно ждёт ~1.9 с анимации чек-листа (без fake-процентов) перед тем, как что-либо `await`-ит результат; если сервер отвечает ошибкой быстрее, промис отклоняется до того, как к нему привязан обработчик, и браузер репортит unhandled rejection, хотя итоговый UI всё равно корректен — исправлено немедленным no-op `.catch()` в момент создания промиса (`trackPending()`), результат всё равно наблюдается позже через `await`;
- в `src/` от предыдущей (уже прерванной) сессии обнаружены и удалены посторонние скомпилированные `.js`/`.d.ts`-файлы, случайно возникшие после раннего некорректного прогона `tsc -b --noEmit false`.

### Какое решение принято

- backend реализован как полностью самостоятельный, framework-независимый слой (`domain/`, `scheduler/`) под сервисной оркестрацией (`services/`) и тонким HTTP-транспортом (`api/`) — та же граница, через которую позже будет вызываться MCP tool, без изменений в domain/scheduler/services;
- dev-only `/changes` endpoint не подключён к production UI и не регистрируется вовсе, если `ENABLE_DEV_ENDPOINTS` не выставлен явно — используется только тестами и ручной curl/httpx-верификацией;
- `frontend/src/lib/diff.ts` и `features/chat/scenarios.ts` не удалены и не тронуты по бизнес-логике — они продолжают обслуживать mock-демонстрацию (все 12 UI-состояний), а server mode использует отдельный, явно промаркированный путь.

### Результат

Backend: `backend/app/{domain,scheduler,services,storage,schemas,api}` + `backend/tests` (79 тестов, все проходят), `backend/pyproject.toml`. Frontend: `frontend/src/api/{client,projects}.ts` + точечные изменения в `App.tsx`, `Dropzone.tsx`, `ImportErrorScreen.tsx`, `features/chat/types.ts`/`ChatPanel.tsx`. Документация: `docs/backend-architecture.md`, `docs/backend-contract-audit.md`, `docs/spikes/backend-core-report.md`, обновлён `README.md`. `npm run build` и `pytest` проходят полностью; канонический сценарий подтверждён на реально запущенных серверах.

### Что требует человеческой проверки

- многопроцессный/multi-worker запуск backend (`--workers > 1`) сломает revision-гарантию `InMemoryProjectStore`, так как `asyncio.Lock` работает только внутри одного event loop — это осознанное MVP-ограничение (product-spec §20), явно задокументированное, но требующее решения перед любым намёком на production-нагрузку;
- warnings из ответа импорта (например, нормализация даты старта проекта, попавшей на выходной) сейчас нигде не отображаются в UI — API их возвращает, но ни один визуальный state их не показывает; решение оставлено как есть, поскольку добавление нового UI-элемента не было частью задачи этого этапа;
- copy-тексты серверных ошибок (`ApiError.message`) идут напрямую в уже существующие визуальные компоненты — стоит сверить тон и формулировки с тем, что раньше было только демонстрационным текстом;
- граница следующего этапа: MCP + OpenRouter должны вызывать `ProjectService.apply_change_set()` через MCP tool boundary, используя тот же контракт, что уже покрыт тестами и dev-endpoint'ом — новый код нужен только для tool-обвязки и реального `/chat` endpoint, самого diff/scheduler/changeset-ядра трогать не потребуется.

---

## Запись 5 — MCP + OpenRouter Agent Integration

### Этап

AI engineering / MCP architecture / agent integration.

### Задача

Добавить настоящий AI Agent layer поверх уже проверенного deterministic backend core: OpenRouter (tool calling), настоящий Model Context Protocol server/client внутри того же FastAPI-процесса, `POST /api/v1/projects/{project_id}/chat`, и минимальную интеграцию с уже реализованным Chat UI — без переделки Scheduler, ChangeSet, Store, Gantt или дизайн-системы.

### Использованный AI-инструмент

Claude Code (Claude Sonnet 5).

### Переданный контекст

- фактический код backend с предыдущего этапа: `ProjectService`, `InMemoryProjectStore` с per-project `asyncio.Lock`, Pydantic-схемы `ChangeSet`/operations, error handlers — явное требование не переписывать их, если они уже удовлетворяют контракту;
- явное требование реально проверить текущий актуальный Python MCP SDK по фактически установленному коду, а не по памяти/угадыванию устаревших методов;
- жёсткое архитектурное ограничение: mutation, запрошенная LLM, обязательно проходит через MCP protocol boundary, а не напрямую через `ProjectService`; AgentService не держит project lock во время OpenRouter-запроса;
- полный список требований к безопасности: model-visible tool schema без `project_id`/`expected_revision`, untrusted tool-call JSON, at most one successful `apply_change_set` за сообщение, prompt injection resistance, no chain-of-thought в истории.

### Промпт

Детальный промпт с ролью «Senior AI Engineer + Python Backend Engineer + MCP Architect»: конкретные env variables (`OPENROUTER_*`, `AGENT_*`, `ENABLE_MCP`), требование реализовать MCP mounting внутри уже существующего FastAPI lifespan без второго процесса/store, allow-list из 4 tools с точными model-visible/wire-схемами, детальный agent loop state machine (revision check → history → OpenRouter → tool calls → at most one mutation → optional wrap-up), требование написать agent-тесты с FakeOpenRouterClient без сети плюс отдельный opt-in live-suite, и явный запрет утверждать, что live natural-language работает, без фактического live-запуска.

### Что предложил AI

- перед установкой SDK — явно проверить актуальные версии `mcp` через PyPI JSON API вместо угадывания; после обнаружения, что `mcp==1.29.0` требует `pydantic>=2.11.0` и конфликтует с уже запиненным `pydantic==2.9.2`/неявным `starlette` диапазоном fastapi — сознательно выбрать точечный минимальный fix (явный pin `starlette==0.38.6`, bump `pydantic`/`uvicorn`) вместо широкого upgrade всего стека, и задокументировать это как demonstrated conflict;
- выбрать `mcp==1.29.0` (последний стабильный релиз линии 1.x), а не только что вышедший `mcp==2.0.0` — 2.0.0 оказался структурно другим релизом с незнакомым dependency-графом (`httpx2`, `mcp-types`, `pyjwt`, `opentelemetry`), и использование его вслепую было бы ровно тем «угадыванием», которого просил избежать промпт;
- реализовать `BoundMcpToolGateway` как отдельный слой между тем, что видит модель (sanitized schema без `project_id`/`expected_revision`), и тем, что реально уходит в MCP (`session.call_tool` с server-side инъекцией этих полей) — вместо того, чтобы пытаться вырезать поля из готовой JSON-схемы во время выполнения;
- построить agent loop как явную последовательность шагов с жёстким правилом «максимум одна успешная mutation», проверяемым кодом, а не только текстом system prompt — второй hallucinated `apply_change_set` физически не может выполниться, так как `tools=None` передаётся в финальный completion после успеха;
- намеренно не использовать `frontend/src/lib/diff.ts` для server-режима — построить отдельный `serverChangeSummaryAdapter`, адаптирующий уже вычисленный backend diff (`direct_changes`/`created_tasks`/...) в существующий frontend `ChangeSet`, вместо повторного вычисления диффа на клиенте.

### Что было проверено вручную

- реальный запуск MCP-сервера под настоящим FastAPI lifespan (`app.router.lifespan_context`) с реальным client/server обменом через Streamable HTTP — session negotiation, `list_tools()` возвращает ровно 4 инструмента, `apply_change_set` мутирует тот же `ProjectService`, повторный вызов со старым `expected_revision` даёт `REVISION_CONFLICT` — всё это через реальный протокол, а не прямой вызов Python-функций;
- полный прогон pytest: 111 passed, 3 skipped (79 baseline без регрессий + 32 новых: MCP tools, agent loop на FakeOpenRouterClient, chat API);
- каноническая AI-команда прогнана через полностью детерминированный, но реалистично сценарированный fake-model loop: 16→18 задач, revision 1→2, релиз 09.11.2026, ровно один successful apply — без единого сетевого вызова;
- frontend-интеграция чата проверена через headless Chrome против реально запущенных backend+frontend: настоящий import, перехват `/chat` только для подстановки АУТЕНТИЧНЫХ backend-ответов (снятых через реальный dev `/changes` endpoint) для applied/clarification/rejected/409-сценариев, и полностью реальный (без перехвата) прогон `AI_NOT_CONFIGURED`, когда backend запущен без ключа;
- live-suite (`tests/test_live_agent.py`) честно помечен и подтверждён как SKIPPED — ключа OpenRouter в этой сессии не было, и это явно зафиксировано, а не выдано за PASS.

### Обнаруженные проблемы

- первая попытка `pip install mcp==1.29.0` без обновления `pyproject.toml` молча подняла `starlette` до `1.6.0`, что сломало совместимость с `fastapi==0.115.0` — обнаружено по предупреждению pip, исправлено пересозданием venv и явным пином версий;
- `mcp.server.fastmcp.FastMCP` при монтировании через `streamable_http_app()` встроенной DNS-rebinding защитой отклоняет заголовок `Host`, если он не соответствует `127.0.0.1:*`/`localhost:*`/`[::1]:*` — попытка использовать вымышленный внутренний хост (`mcp.internal`) и даже голый `localhost` без порта давали HTTP 421; исправлено использованием `http://localhost:8000/` как base URL для внутреннего ASGI-транспорта;
- при пробросе исключения (`AgentStepLimitError` и т.п.) через вложенные `async with` MCP-клиента, `anyio`-task group оборачивала его в `BaseExceptionGroup`, из-за чего `except AgentError: raise` переставал совпадать и ошибка ошибочно превращалась в `McpUnavailableError` — обнаружено интеграционными тестами (`test_max_steps_reached...`, `test_provider_timeout...`), исправлено явной рекурсивной распаковкой single-exception group;
- `streamablehttp_client` (используемый изначально по памяти) оказался помечен `@deprecated` в установленной версии SDK — обнаружено по warning в выводе pytest, мигрировано на актуальный `streamable_http_client` с явно создаваемым `httpx.AsyncClient`;
- после интеграции frontend-чата Gantt не подсвечивал изменения в server-режиме, хотя ChangeSummary в чате отображался верно — top-level `changeSet`, который получает `<Workspace>`/`<GanttView>`, был захардкожен в `null` для `dataSource==='server'` и не обновлялся из результата чата; исправлено добавлением состояния `serverChangeSet`, использующего тот же объект, что и адаптер для чата.

### Какое решение принято

- MCP-сервер использует один и тот же процесс/`InMemoryProjectStore`, что и REST API — второй backend-процесс не создаётся;
- `AgentService` подключается к смонтированному MCP-серверу через `httpx.ASGITransport` (in-process), а не через реальный TCP-запрос на собственный `localhost:8000` — сознательный выбор ради устойчивости внутри одного event loop, при этом `/mcp` остаётся реально смонтированным и доступным снаружи для ручной проверки/будущего внешнего клиента;
- backend diff (`ChangeSummary`) и frontend mock diff (`lib/diff.ts`) остаются двумя независимыми источниками истины — адаптер (`serverChangeSummaryAdapter.ts`) конвертирует форму данных, но не пересчитывает классификацию заново;
- dev-only `/changes` endpoint не подключён к AgentService и не используется production-чатом — оба пути (dev endpoint и MCP tool) независимо вызывают один и тот же `ProjectService.apply_change_set()`.

### Результат

Backend: `backend/app/agent/*` (system_prompt, openrouter_client, gateway, conversation_store, service), `backend/app/mcp_server/*` (app, tools, schemas), новый `POST /chat` router и schemas, точечное расширение `ProjectService.apply_change_set()` (добавлен `client_ref_map` в результат). 32 новых теста (111 всего, 3 live честно skipped). Frontend: `api/chat.ts`, `app/serverChangeSummaryAdapter.ts`, точечные изменения в `App.tsx` (реальный chat send, revision-conflict handling, Gantt highlighting из server diff). Документация: `docs/mcp-agent-architecture.md`, `docs/agent-system-prompt.md`, `docs/spikes/mcp-agent-report.md`, обновлён `README.md`.

### Что требует человеческой проверки

- реальное поведение конкретной OpenRouter-модели (следование system prompt, качество clarification-вопросов, устойчивость к prompt injection на живых данных) — механизм проверен полностью, поведение конкретной модели не проверено ни разу вживую в этой сессии;
- `/mcp` endpoint не имеет аутентификации — приемлемо для локального тестового задания, но явно небезопасно для публичного deployment; зафиксировано как production TODO в `docs/mcp-agent-architecture.md`;
- многопроцессный запуск (`--workers > 1`) сломает как revision-гарантию, так и MCP session manager — то же ограничение, что и раньше, актуально вдвойне;
- стоимость реальных вызовов OpenRouter не протестирована на реальном трафике — только теоретические границы (`AGENT_MAX_STEPS`, `AGENT_MAX_READ_TOOL_CALLS`) заложены в код.

---

# Шаблон следующей записи

## Запись N — Название этапа

### Этап

### Задача

### Использованный AI-инструмент

### Переданный контекст

### Промпт

### Что предложил AI

### Что было проверено вручную

### Обнаруженные проблемы

### Какое решение принято

### Результат

# AI Gantt Planner — Product, Business and System Specification v0.3

**Статус:** утверждённая спецификация MVP  
**Назначение:** единый источник требований для design-, frontend-, backend-, QA- и AI-агентов  
**Язык интерфейса:** русский  
**Язык API, моделей данных и исходного кода:** английский  
**Версия:** 0.3

## 1. Цель продукта

Создать веб-приложение, которое позволяет:

1. загрузить проектный план из Excel;
2. проверить корректность данных;
3. автоматически рассчитать расписание;
4. отобразить план в виде диаграммы Гантта;
5. открыть детали любой задачи;
6. изменить план через естественно-языковую команду;
7. преобразовать команду в структурированный change set;
8. применить изменения через MCP;
9. автоматически пересчитать зависимые задачи;
10. мгновенно обновить интерфейс;
11. показать пользователю результат и влияние изменений;
12. экспортировать актуальный план обратно в Excel.

Ключевой принцип:

> LLM интерпретирует намерение пользователя. Backend контролирует данные, бизнес-правила и итоговое состояние проекта.

## 2. Канонический предметный контекст

Для демонстрации используется реальный тип задачи из продуктовой практики: проектирование и выпуск функционала **карточки пациента для платформы стоматологов**.

Команда:

- **Анна П** — Project Manager / Discovery;
- **Елена** — Product Designer;
- **Василий** — Backend Developer;
- **Дмитрий** — Frontend Developer;
- **Анна С** — QA Engineer.

Текущая стадия: сбор, анализ и согласование требований к карточке пациента и расписанию врача.

## 3. Scope MVP

MVP MUST поддерживать:

- загрузку `.xlsx`;
- выбор даты начала проекта;
- проверку обязательных колонок и строк;
- отдельный проект на каждый импорт;
- до 500 задач;
- расчёт рабочих дат;
- Finish-to-Start зависимости;
- несколько предшественников;
- диаграмму Гантта;
- dependency arrows;
- read-only modal задачи;
- AI-чат;
- изменение длительности;
- перенос задачи;
- изменение исполнителя;
- массовую замену исполнителя;
- создание одной или нескольких задач;
- изменение зависимостей;
- создание параллельных веток;
- автоматический пересчёт downstream-задач;
- атомарность составной команды;
- revision control;
- уточнение неоднозначных запросов;
- отображение direct / created / derived changes;
- экспорт Excel;
- OpenRouter через API;
- реальное использование MCP.

## 4. Out of Scope MVP

Не входят:

- регистрация и авторизация;
- роли и права;
- production persistence;
- история версий;
- undo/redo;
- статусы и проценты выполнения;
- несколько исполнителей у одной задачи;
- resource capacity planning;
- праздники и персональные календари;
- SS/FF/SF зависимости;
- lag/lead;
- critical path;
- drag-and-drop редактирование;
- inline editing;
- Jira/Linear/Asana/MS Project integrations;
- полноценная мобильная версия.

## 5. Модель рабочего дня и трудоёмкости

Основное правило:

```text
1 рабочий день = 8 плановых человеко-часов одного исполнителя
```

Backend constant:

```text
HOURS_PER_WORKDAY = 8
```

Производное значение:

```text
planned_effort_hours = duration_workdays × 8
```

Правила:

- хранится `duration_workdays`;
- `planned_effort_hours` вычисляется;
- один исполнитель считается выделенным на задачу на 100%;
- дробные рабочие дни не поддерживаются;
- если над этапом работают два разработчика, создаются две отдельные задачи.

## 6. Доменная модель

### Project

```text
Project
- id: UUID
- name: string
- project_start_date: date
- revision: integer
- tasks: Task[]
- created_at: datetime
- updated_at: datetime
```

### Task

```text
Task
- id: UUID
- name: string
- description: string
- assignee: string | null
- duration_workdays: integer
- planned_effort_hours: integer
- predecessor_ids: UUID[]
- start_not_before: date | null
- start_date: date
- end_date: date
- display_order: integer
- created_source: "import" | "agent"
```

`successor_ids` является производным полем API DTO.

## 7. Входной Excel

Обязательные колонки:

```text
Задача
Описание
Исполнитель
Длительность
Предшественники
```

Ограничения:

- только `.xlsx`;
- максимум 5 MB;
- максимум 500 задач;
- используется первый непустой worksheet;
- формулы в обязательных полях не поддерживаются.

### Задача

- обязательна;
- 1–200 символов;
- уникальна после нормализации;
- `;` запрещён.

### Описание

- необязательно;
- максимум 2000 символов.

### Исполнитель

- один исполнитель;
- пустое значение → `null`.

### Длительность

- целое число 1–365;
- интерпретируется как рабочие дни.

### Предшественники

- необязательно;
- несколько задач разделяются `;`;
- ссылки разрешаются по полному нормализованному названию;
- после импорта преобразуются в UUID.

## 8. Правила Scheduler

Рабочий календарь:

- понедельник–пятница — рабочие;
- суббота и воскресенье — выходные;
- праздники не учитываются;
- даты date-only.

Дата проекта задаётся при импорте.

Если дата старта на выходном — нормализуется вперёд до ближайшего рабочего дня.

День начала входит в длительность:

```text
end_date = start_date + (duration_workdays - 1) рабочих дней
```

Для задачи без predecessors:

```text
dependency_earliest_start = project_start_date
```

Для задачи с predecessors:

```text
dependency_earliest_start =
первый рабочий день после самого позднего end_date predecessors
```

Итог:

```text
start_date = max(dependency_earliest_start, start_not_before)
```

Scheduler MUST:

1. построить directed graph;
2. проверить cycle;
3. выполнить topological sort;
4. рассчитать даты;
5. рассчитать `planned_effort_hours`.

## 9. Правила изменения задач

### Длительность

Команда:

> Увеличь Frontend-разработку до 8 рабочих дней.

Результат:

```text
duration_workdays = 8
planned_effort_hours = 64
```

### Человеко-часы

Команда:

> Установи трудоёмкость задачи в 24 человеко-часа.

Результат:

```text
duration_workdays = 3
```

Часы должны делиться на 8 без остатка.

### Перенос

> Перенеси задачу на 3 рабочих дня позже.

Backend задаёт `start_not_before` относительно snapshot до change set.

Если перенос раньше нарушает dependency — операция отклоняется.

### Неделя

```text
1 неделя = 5 рабочих дней
```

## 10. Создание и изменение зависимостей

### Создать после задачи

Новая задача получает указанную задачу в predecessors, существующие successors не меняются.

### Вставить между A и B

До:

```text
A → B
```

После:

```text
A → C → B
```

Разрешено только при прямой связи A → B.

### Параллельные задачи

Для нескольких исполнителей создаются отдельные параллельные задачи.

Пример:

```text
Согласование разработки
        ↓
 ┌──────┴────────┐
 ↓               ↓
Правки backend   Правки frontend
 └──────┬────────┘
        ↓
        QA
```

## 11. Атомарность

Один пользовательский запрос = один change set.

Backend:

1. создаёт working copy;
2. валидирует операции;
3. разрешает client references;
4. применяет операции к копии;
5. проверяет граф;
6. запускает Scheduler;
7. формирует diff;
8. сохраняет только при полном успехе.

Если одна операция невалидна:

- ничего не применяется;
- revision не меняется.

## 12. Client references

Для новых задач внутри одного change set используется временный `client_ref`.

```text
TaskRef =
  { "task_id": UUID }
  OR
  { "client_ref": string }
```

`client_ref`:

- уникален внутри change set;
- не сохраняется в Project;
- используется для ссылок на ещё не созданные задачи.

## 13. AI-архитектура

LLM отвечает за:

- понимание сообщения;
- поиск нужных задач;
- выбор MCP tools;
- аргументы tool calls;
- запрос уточнения;
- краткий ответ.

Backend отвечает за:

- источник истины;
- UUID;
- валидацию;
- атомарность;
- Scheduler;
- dependencies;
- revision;
- import/export;
- person-hours;
- diff.

LLM MUST NOT:

- переписывать Project JSON напрямую;
- рассчитывать даты;
- назначать UUID;
- округлять часы;
- обходить MCP;
- изменять неоднозначную задачу;
- раскрывать API key или chain-of-thought.

## 14. MCP tools

Read tools:

```text
get_project_outline
get_task_details
search_tasks
```

Mutation tool:

```text
apply_change_set
```

Поддерживаемые operations:

```text
update_task_fields
change_duration
move_task
create_task
insert_task_between
set_predecessors
add_dependency
remove_dependency
bulk_set_assignee
clear_start_constraint
```

Agent Orchestrator MUST выполнять mutation через MCP Client, а не напрямую через ProjectService.

## 15. REST API

Base:

```text
/api/v1
```

Endpoints:

```text
POST /api/v1/projects/import
GET  /api/v1/projects/{project_id}
POST /api/v1/projects/{project_id}/chat
GET  /api/v1/projects/{project_id}/export
GET  /api/v1/health
```

Chat request:

```json
{
  "message": "Увеличь Frontend-разработку до 8 рабочих дней",
  "conversation_id": null,
  "expected_revision": 1
}
```

Статусы ответа:

```text
applied
clarification_required
rejected
```

Revision conflict → HTTP 409.

## 16. Frontend UX

### Empty state

- название продукта;
- краткое объяснение;
- dropzone;
- file picker;
- дата начала;
- ссылка на sample Excel;
- требования к файлу;
- кнопка импорта.

### Workspace

```text
┌────────────────────────────────────────────────────┐
│ Header                                             │
│ Project name     Start date     Upload     Export   │
├─────────────────────────────────┬──────────────────┤
│                                 │                  │
│          Gantt area             │     AI Chat      │
│                                 │                  │
└─────────────────────────────────┴──────────────────┘
```

Пропорция:

```text
Gantt: 70–75%
Chat: 25–30%
```

### Gantt

MUST:

- scroll;
- dependency arrows;
- click по строке / bar;
- read-only modal;
- selected state;
- change highlighting.

MUST NOT:

- drag-and-drop;
- resize;
- inline edit.

### Modal

Показывает:

- название;
- описание;
- исполнителя;
- source;
- длительность;
- planned effort;
- start/end;
- start constraint;
- predecessors;
- successors.

### Change types

UI различает:

- direct;
- created;
- derived.

Различия не должны основываться только на цвете.

## 17. Канонический sample Excel

Файл:

```text
examples/sample_patient_card_project.xlsx
```

Дата старта:

```text
07.09.2026
```

До канонической команды: 16 задач.

После команды: 18 задач.

## 18. Каноническая AI-команда

> Согласование требований к карточке пациента и расписанию врача займёт на 2 рабочих дня больше. Увеличь Frontend-разработку карточки пациента до 8 рабочих дней. После Согласования результата разработки добавь две параллельные задачи: «Правки backend по итогам согласования» на 2 рабочих дня для Василия и «Правки frontend по итогам согласования» на 3 рабочих дня для Дмитрия. QA-тестирование карточки пациента должно начинаться после завершения обеих задач.

Ожидаемый результат:

- согласование требований: 3 → 5 дней;
- frontend: 7 → 8 дней;
- создаются 2 параллельные задачи;
- QA зависит от обеих;
- revision: 1 → 2;
- релиз: `02.11.2026 → 09.11.2026`.

## 19. Экспорт

Sheet `План`:

```text
Задача
Описание
Исполнитель
Длительность
Предшественники
Плановая трудоёмкость, ч
Дата начала
Дата окончания
Не ранее
```

Sheet `Метаданные`:

```text
project_name
project_start_date
revision
exported_at_utc
```

## 20. Project Store MVP

Допустим:

```text
InMemoryProjectStore
```

Правила:

- `project_id → Project`;
- `conversation_id → ChatHistory`;
- каждый импорт создаёт отдельный UUID;
- backend работает в одном worker;
- данные теряются при restart.

## 21. Безопасность

- OpenRouter API key только на backend;
- `.env` не коммитится;
- `.env.example` без секретов;
- MCP allow-list;
- input file validation;
- production CORS только для известного origin;
- содержимое Excel считается недоверенными данными.

## 22. Acceptance Criteria

MVP MUST проходить минимум:

1. sample Excel импортируется;
2. 1 день = 8 часов;
3. 24 часа = 3 дня;
4. 12 часов не округляются молча;
5. один assignee на задачу;
6. weekend scheduling корректен;
7. multiple predecessors корректны;
8. cycle полностью отклоняет change set;
9. изменение duration пересчитывает effort и downstream;
10. одна команда создаёт две параллельные задачи;
11. client refs работают в том же atomic change set;
12. rollback полный;
13. revision 1 → 2;
14. ambiguity не вызывает mutation;
15. modal показывает duration и effort;
16. Gantt обновляется без reload;
17. direct/created/derived различимы;
18. после канонической команды релиз = `09.11.2026`;
19. export содержит 18 задач;
20. API key отсутствует во frontend и network responses.

## 23. Требования к тестам

### Scheduler

- linear chain;
- parallel branches;
- multiple predecessors;
- weekends;
- start constraint;
- move earlier/later;
- cycle;
- canonical schedule.

### Effort

- 1 day = 8 h;
- 3 days = 24 h;
- set 24 h;
- add 16 h;
- reject 12 h.

### Import

- valid sample;
- missing column;
- duplicate name;
- invalid duration;
- unknown predecessor;
- self-dependency;
- cycle;
- formula.

### Change set

- multi-operation success;
- rollback;
- client refs;
- unresolved/duplicate client ref;
- revision increment/conflict;
- parallel task creation;
- canonical change set.

### E2E

```text
upload sample Excel
→ render Gantt
→ send canonical command
→ verify two new tasks
→ verify release date
→ open modal
→ export Excel
```

## 24. Definition of Done

MVP готов, когда:

- выполнены acceptance criteria;
- sample Excel импортируется;
- каноническая команда выполняется одной отправкой;
- создаются две параллельные задачи;
- QA переподключается;
- релиз = `09.11.2026`;
- Gantt обновляется без reload;
- modal работает;
- export работает;
- MCP реально используется;
- OpenRouter key защищён;
- приложение развёрнуто;
- README позволяет запустить проект;
- demo показывает основной flow;
- Roadmap to production присутствует;
- основные тесты проходят.

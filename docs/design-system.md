# PlanPilot — Design System

Источник истины для визуального языка high-fidelity прототипа AI Gantt Planner. Все значения определены как CSS custom properties в [`frontend/src/styles/tokens.css`](../frontend/src/styles/tokens.css) — компоненты и feature-стили не должны использовать «сырые» hex-значения или произвольные размеры в обход токенов.

Тема — только светлая (LIGHT). Тёмная тема, glassmorphism, glow-эффекты и фиолетовые AI-градиенты сознательно исключены — см. `docs/design-decisions.md`.

## 1. Цвет

### Поверхности и структура

| Токен | Значение | Назначение |
|---|---|---|
| `--color-background` | `#f6f7f9` | Фон страницы/workspace — лёгкий серый, отделяет белые панели без теней |
| `--color-surface` | `#ffffff` | Рабочие поверхности: панели, модалки, header |
| `--color-surface-subtle` | `#fbfbfc` | Второй уровень поверхности (легенда, карточки внутри chat) |
| `--color-surface-sunken` | `#f2f3f6` | Заглублённые элементы (disabled-поля, иконки-плашки) |
| `--color-surface-hover` / `-active` | `#f4f5f7` / `#ebedf1` | Ховер/активное состояние строк и кнопок |
| `--color-surface-inverse` | `#1a1d21` | Инверсная поверхность — тёмные tooltip и dev-панель |
| `--color-border` / `-subtle` / `-strong` | `#e5e7eb` / `#eef0f2` / `#d2d6dd` | Три веса границ — от почти незаметной до чёткой |

### Текст

| Токен | Значение |
|---|---|
| `--color-text-primary` | `#14171a` — почти чёрный, максимальная читаемость |
| `--color-text-secondary` | `#596170` |
| `--color-text-muted` | `#8b929e` |
| `--color-text-inverse` / `-on-accent` | `#ffffff` |

### Accent

Один акцентный цвет во всём продукте — `--color-accent: #2f5fe0`. Используется только для primary-действий, фокуса и выбора. Сознательно **не используется** для баров задач на Гантте, чтобы не конкурировать с цветами AI-изменений.

### Semantic

`--color-success`, `--color-warning`, `--color-error` — с парными `-soft` (фон) и `-border` вариантами для Alert/Badge.

### Семантика AI-изменений

Три отдельных оттенка, каждый — с собственной парой «насыщенный / мягкий» и «bar / bar-hover»:

| Тип | Токен (акцент) | Токен (бар) | Label | Иконка |
|---|---|---|---|---|
| `direct` — прямое изменение | `--color-change-direct` (`#b7791f`, янтарь) | `--color-change-direct-bar` | «Изменено» | `PencilLine` |
| `created` — создано AI | `--color-change-created` (`#0d7d64`, тил) | `--color-change-created-bar` | «Новая» | `Plus` |
| `derived` — пересчитано | `--color-change-derived` (`#3e62c8`, синий) | `--color-change-derived-bar` | «Пересчитано» | `RefreshCw` |

**Важное правило:** ни один из трёх типов не полагается только на цвет. Каждый несёт минимум два независимых сигнала: цвет + иконка-маркер + подпись (в легенде/badge) + для `derived` дополнительно диагональная штриховка бара. Это закреплено в единственном источнике — `CHANGE_META` в [`components/ChangeMarker.tsx`](../frontend/src/components/ChangeMarker.tsx).

## 2. Типографика

Шрифт — системный стек (`-apple-system, 'Segoe UI', Roboto…`), моноширинный — только для dev-инструментов (`--font-mono`).

| Стиль | Размер / high | Вес | Применение |
|---|---|---|---|
| Page title | 24 / 32 | 600 | Заголовок Import screen |
| Section title | 15 / 20 | 600 | Заголовки секций, названия панелей |
| Body | 14 / 20 | 400 | Основной текст |
| Small | 13 / 18 | 400 | Вторичный текст, подписи полей |
| Table | 13 / 18 | 400 | Ячейки таблицы задач |
| Label | 11 / 14 | 600, uppercase, `+0.045em` | Заголовки колонок, лейблы полей |
| Micro | 10 / 13 | 400 | Легенда, day-of-week в Гантте |

Числа везде выводятся с `font-variant-numeric: tabular-nums` — даты и часы в таблице не «прыгают» по ширине.

## 3. Spacing

Шкала на базе 2px, 13 шагов от `--space-1` (2px) до `--space-13` (64px). Внутри компонентов использованы `--space-3…6` (6–12px), между секциями — `--space-7…9` (16–24px). Никаких «магических» px вне шкалы.

## 4. Radius

Сдержанный B2B-радиус: `--radius-xs` (3px) для мелких элементов (маркеры, badge) → `--radius-xl` (12px) для модалок и import-карточки. Максимум — 12px, кроме pill-элементов (чипы, DEV-toggle).

## 5. Тени

Минимальные, только там, где элемент реально «парит» над страницей: `--shadow-xs` на кнопках/dropzone, `--shadow-md` на tooltip, `--shadow-lg` на модалках. Панели (Gantt, Chat) держатся на границе (`border`), а не на тени — это ключевая часть «плоского», не «карточного» ощущения инструмента.

## 6. Компоненты

Переиспользуемые UI-примитивы — `frontend/src/components/`:

`Button`, `IconButton`, `Badge`, `Input`, `Textarea`, `DateInput`, `Dropzone`, `Tooltip`, `Modal`, `Alert`, `TaskChip`, `ProjectMetric`, `ChangeMarker`/`ChangeBadge`.

Продуктовые (feature-специфичные) компоненты, собранные поверх примитивов:

- `features/gantt/GanttView` — таблица задач + timeline + SVG-стрелки зависимостей;
- `features/chat/ChatPanel` — AI-чат (empty state, thread, composer);
- `features/change-summary/ChangeSummary` — «Изменено / Добавлено / Пересчитано» + Release impact;
- `features/task-modal/TaskDetailsModal` — read-only карточка задачи;
- `features/import/*` — три экрана импорта.

Правила:
- Стили — CSS Modules, один модуль на компонент, без глобальных селекторов кроме `styles/global.css` и `reset.css`.
- Иконки — только `lucide-react`, размеры 11–18px в зависимости от контекста.
- Ни один компонент не хранит бизнес-логику планирования — только форматирование и отображение переданных данных (см. `docs/design-decisions.md`, раздел о границе frontend/backend).

## 7. Плотность интерфейса

Строка Гантта — 32px, ряд таблицы задач — та же высота, без карточек на задачу. Это осознанный выбор: продукт должен одинаково хорошо читаться и при 16, и при 18+ задачах на экране без прокрутки. Подробности компромиссов — в `docs/design-decisions.md`.

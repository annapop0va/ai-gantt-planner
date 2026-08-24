# Демо AI Gantt Planner

[Смотреть демо-видео](https://flonnect.com/video/6ebbb0d0bbaf-4fd4-9823-15553eb6ea99)

В видео показан основной end-to-end сценарий работы продукта:

Excel → построение Gantt → изменение плана через AI-чат → пересчёт расписания → экспорт Excel.

## Что показано в демо

1. Загрузка тестового Excel с проектным планом.
2. Построение исходного Gantt:
   - 16 задач;
   - дата релиза 02.11.2026.
3. Отправка составной команды естественным языком через AI-чат.
4. Применение изменений через Agent → MCP → ChangeSet → Scheduler.
5. Обновление проектного плана:
   - 18 задач;
   - дата релиза 09.11.2026.
6. Отображение Change Summary.
7. Экспорт обновлённого плана обратно в Excel.

## Материалы

Тестовый Excel:
[examples/sample_patient_card_project.xlsx](examples/sample_patient_card_project.xlsx)

Публичная версия приложения:
https://ai-gantt-planner-2.onrender.com

Roadmap:
[docs/roadmap-to-production.md](docs/roadmap-to-production.md)

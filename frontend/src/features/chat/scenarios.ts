/**
 * Canned copy and reply classification for the chat prototype.
 *
 * There is no real language model here — only one real transformation exists
 * in the fixtures (`mock_project_before.json` → `mock_project_after.json`), so
 * any message that is not deliberately steered toward a specific failure mode
 * resolves to that one canonical change set. The three failure-mode triggers
 * ("api", "qa" + a move, an explicit error word) exist so a reviewer can reach
 * every required chat state through the real input box, not only through the
 * dev state switcher.
 */

export const CANONICAL_COMMAND =
  'Согласование требований к карточке пациента и расписанию врача займёт на 2 рабочих дня больше. ' +
  'Увеличь Frontend-разработку карточки пациента до 8 рабочих дней. ' +
  'После Согласования результата разработки добавь две параллельные задачи: ' +
  '«Правки backend по итогам согласования» на 2 рабочих дня для Василия и ' +
  '«Правки frontend по итогам согласования» на 3 рабочих дня для Дмитрия. ' +
  'QA-тестирование карточки пациента должно начинаться после завершения обеих задач.'

export const SUGGESTED_PROMPTS = [
  'Перенести задачу',
  'Изменить исполнителя',
  'Добавить этап',
  'Изменить зависимости',
]

export interface ExamplePrompt {
  text: string
  /** Complete commands can run immediately; short starters only fill the input. */
  runImmediately: boolean
}

export const EXAMPLE_PROMPTS: ExamplePrompt[] = [
  { text: 'Увеличь backend-разработку на 2 дня', runImmediately: true },
  { text: 'Передай QA-задачи Анне С', runImmediately: true },
]

export type ChatOutcome = 'success' | 'clarification' | 'rejected' | 'error'

export function classifyMessage(text: string): ChatOutcome {
  const normalized = text.toLowerCase()

  if (normalized.includes('api')) return 'clarification'
  if (normalized.includes('недоступ') || normalized.includes('серверная ошибка')) return 'error'
  if (
    normalized.includes('qa') &&
    (normalized.includes('перенес') || normalized.includes('дату') || normalized.includes('раньше'))
  ) {
    return 'rejected'
  }

  return 'success'
}

export const CLARIFICATION_REPLY =
  'Нашёл несколько задач с «API» в названии: API Integration, API Testing, API Documentation. Какую из них перенести?'

export const REJECTED_REPLY =
  'Изменения не применены. QA-тестирование нельзя перенести на эту дату: оно зависит от завершения frontend- и backend-правок.'

export const ERROR_REPLY =
  'Не удалось обработать запрос. Сервис AI временно недоступен. Ваш проект не изменён.'

export const SUCCESS_REPLY = 'Готово. План обновлён.'

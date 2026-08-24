export interface RequiredColumn {
  name: string
  hint: string
}

export const REQUIRED_COLUMNS: RequiredColumn[] = [
  { name: 'Задача', hint: 'название, 1–200 символов' },
  { name: 'Описание', hint: 'необязательно' },
  { name: 'Исполнитель', hint: 'один человек на задачу' },
  { name: 'Длительность', hint: 'рабочие дни, 1–365' },
  { name: 'Предшественники', hint: 'через «;», по названию' },
]

export interface ImportIssue {
  /** Some structural backend errors (missing column, dependency cycle) have no single row. */
  row: number | null
  field: string | null
  message: string
}

/** Deterministic demo issues — shown when a picked file name signals a bad import. */
export const DEMO_IMPORT_ISSUES: ImportIssue[] = [
  { row: 4, field: 'Длительность', message: 'Значение должно быть целым числом от 1 до 365' },
  { row: 9, field: 'Предшественники', message: 'Задача «Тестирование API» не найдена в файле' },
  { row: 12, field: 'Задача', message: 'Название повторяется в строке 12 и строке 15' },
]

const ERROR_TRIGGER_WORDS = ['error', 'invalid', 'bad', 'ошибка', 'некоррект']

/** Lets a reviewer reach the Import Error state through the real dropzone. */
export function looksInvalid(fileName: string): boolean {
  const lower = fileName.toLowerCase()
  if (!lower.endsWith('.xlsx')) return true
  return ERROR_TRIGGER_WORDS.some((word) => lower.includes(word))
}

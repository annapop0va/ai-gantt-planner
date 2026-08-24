import type { IsoDate } from '@/types/project'

/**
 * Date helpers for a date-only, Mon–Fri working calendar (product-spec §8).
 *
 * The frontend does not schedule anything — every date it renders comes from
 * the backend DTO. These helpers only *read* those dates: formatting them for
 * Russian UI copy and measuring the distance between two of them so the change
 * summary can say "+5 рабочих дней".
 */

const MONTHS_GENITIVE = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
]

const MONTHS_SHORT = [
  'янв', 'фев', 'мар', 'апр', 'мая', 'июн',
  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
]

const MONTHS_NOMINATIVE = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

const WEEKDAYS_SHORT = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']

/** Parse `YYYY-MM-DD` into a local midnight Date, free of timezone drift. */
export function parseIso(iso: IsoDate): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function toIso(date: Date): IsoDate {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

export function isWeekend(date: Date): boolean {
  const day = date.getDay()
  return day === 0 || day === 6
}

export function addDays(date: Date, days: number): Date {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

/** `7 сентября 2026` */
export function formatLong(iso: IsoDate): string {
  const d = parseIso(iso)
  return `${d.getDate()} ${MONTHS_GENITIVE[d.getMonth()]} ${d.getFullYear()}`
}

/** `2 ноября` — no year, for in-context references. */
export function formatDayMonthLong(iso: IsoDate): string {
  const d = parseIso(iso)
  return `${d.getDate()} ${MONTHS_GENITIVE[d.getMonth()]}`
}

/** `5 окт` — compact, for metrics and tooltips. */
export function formatShort(iso: IsoDate): string {
  const d = parseIso(iso)
  return `${d.getDate()} ${MONTHS_SHORT[d.getMonth()]}`
}

/** `5 окт — 14 окт` */
export function formatRange(startIso: IsoDate, endIso: IsoDate): string {
  return `${formatShort(startIso)} — ${formatShort(endIso)}`
}

export function monthNameNominative(monthIndex: number): string {
  return MONTHS_NOMINATIVE[monthIndex]
}

export function weekdayShort(date: Date): string {
  return WEEKDAYS_SHORT[date.getDay()]
}

/**
 * Working days from `fromIso` (exclusive) to `toIso` (inclusive).
 * Negative when `toIso` is earlier. Used for "+5 рабочих дней" style deltas.
 */
export function workdaysBetween(fromIso: IsoDate, toIso: IsoDate): number {
  const from = parseIso(fromIso)
  const to = parseIso(toIso)
  if (from.getTime() === to.getTime()) return 0

  const forward = to > from
  const step = forward ? 1 : -1
  let cursor = new Date(forward ? from : to)
  const target = forward ? to : from
  let count = 0

  while (cursor < target) {
    cursor = addDays(cursor, 1)
    if (!isWeekend(cursor)) count += 1
  }
  return count * step
}

/** Every Mon–Fri date in `[startIso, endIso]`, inclusive. */
export function eachWorkday(startIso: IsoDate, endIso: IsoDate): Date[] {
  const out: Date[] = []
  const end = parseIso(endIso)
  let cursor = parseIso(startIso)
  while (cursor <= end) {
    if (!isWeekend(cursor)) out.push(new Date(cursor))
    cursor = addDays(cursor, 1)
  }
  return out
}

/* -----------------------------------------------------------------------------
 * Russian pluralisation
 * -------------------------------------------------------------------------- */

/** `plural(3, ['задача', 'задачи', 'задач']) === 'задачи'` */
export function plural(n: number, forms: [string, string, string]): string {
  const abs = Math.abs(n) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return forms[2]
  if (last > 1 && last < 5) return forms[1]
  if (last === 1) return forms[0]
  return forms[2]
}

export const pluralTasks = (n: number) => plural(n, ['задача', 'задачи', 'задач'])
export const pluralWorkdays = (n: number) => plural(n, ['день', 'дня', 'дней'])
export const pluralWorking = (n: number) => plural(n, ['рабочий', 'рабочих', 'рабочих'])
export const pluralReceived = (n: number) => plural(n, ['получила', 'получили', 'получили'])
export const pluralSubsequent = (n: number) =>
  plural(n, ['последующая', 'последующие', 'последующих'])

/** `8 дн.` — the compact table form. */
export function formatDurationShort(workdays: number): string {
  return `${workdays} дн.`
}

/** `8 рабочих дней · 64 ч` — the explicit tooltip/modal form. */
export function formatDurationFull(workdays: number, hours: number): string {
  return `${workdays} ${pluralWorking(workdays)} ${pluralWorkdays(workdays)} · ${hours} ч`
}

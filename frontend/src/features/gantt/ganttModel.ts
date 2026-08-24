import type { ChangeSet, ChangeType, IsoDate, Project, Task } from '@/types/project'
import { addDays, eachWorkday, isWeekend, monthNameNominative, parseIso, toIso, weekdayShort } from '@/lib/date'

/**
 * Gantt view model.
 *
 * This module is the *only* place that knows how a Project DTO becomes chart
 * geometry. Components below it deal in column indices and row indices, never
 * in dates. That boundary is what makes the hand-rolled chart replaceable: to
 * adopt a real Gantt library later, rewrite the renderer against this same
 * model (or map this model to the library's own task/link shape) and leave the
 * rest of the workspace untouched.
 *
 * Deliberate modelling choice: **only working days get a column.** The whole
 * domain is expressed in working days (1 day = 8 person-hours, Mon–Fri), so
 * weekend columns would be dead pixels that push the release date off-screen.
 * Week boundaries are drawn as separators instead, which keeps the calendar
 * readable without spending 2/7 of the width on nothing.
 */

export interface DayColumn {
  iso: IsoDate
  date: Date
  dayOfMonth: number
  monthIndex: number
  weekday: string
  /** Monday — where a week separator is drawn. */
  isWeekStart: boolean
}

export interface HeaderGroup {
  key: string
  label: string
  startIndex: number
  span: number
}

export interface GanttRow {
  task: Task
  rowIndex: number
  startIndex: number
  span: number
  changeType: ChangeType | null
  /** Where the bar sat before the last AI command, for the ghost outline. */
  ghost: { startIndex: number; span: number } | null
}

export type LinkKind = 'normal' | 'added' | 'removed'

export interface GanttLink {
  id: string
  sourceId: string
  targetId: string
  kind: LinkKind
}

export interface GanttModel {
  days: DayColumn[]
  months: HeaderGroup[]
  rows: GanttRow[]
  rowById: Map<string, GanttRow>
  links: GanttLink[]
  columnCount: number
}

/** Working days of head/tail padding so bars and arrows are not flush to the edge. */
const TRAILING_PADDING_DAYS = 3

export function buildGanttModel(project: Project, changeSet: ChangeSet | null): GanttModel {
  const rangeSource: IsoDate[] = []
  for (const task of project.tasks) {
    rangeSource.push(task.start_date, task.end_date)
  }
  if (changeSet) {
    for (const prev of Object.values(changeSet.previousSchedule)) {
      rangeSource.push(prev.start, prev.end)
    }
  }

  const days = buildColumns(rangeSource)
  const indexByIso = new Map(days.map((day, index) => [day.iso, index]))

  /** Nearest column at or after `iso` — guards against any non-working date. */
  const columnFor = (iso: IsoDate): number => {
    const exact = indexByIso.get(iso)
    if (exact !== undefined) return exact
    let cursor = parseIso(iso)
    for (let i = 0; i < 14; i += 1) {
      const found = indexByIso.get(toIso(cursor))
      if (found !== undefined) return found
      cursor = addDays(cursor, 1)
    }
    return 0
  }

  const ordered = [...project.tasks].sort((a, b) => a.display_order - b.display_order)

  const rows: GanttRow[] = ordered.map((task, rowIndex) => {
    const startIndex = columnFor(task.start_date)
    const endIndex = columnFor(task.end_date)
    const previous = changeSet?.previousSchedule[task.id] ?? null

    return {
      task,
      rowIndex,
      startIndex,
      span: Math.max(1, endIndex - startIndex + 1),
      changeType: changeSet?.byTask[task.id] ?? null,
      ghost: previous
        ? {
            startIndex: columnFor(previous.start),
            span: Math.max(1, columnFor(previous.end) - columnFor(previous.start) + 1),
          }
        : null,
    }
  })

  const rowById = new Map(rows.map((row) => [row.task.id, row]))

  return {
    days,
    months: groupByMonth(days),
    rows,
    rowById,
    links: buildLinks(project, changeSet, rowById),
    columnCount: days.length,
  }
}

/** Working-day columns spanning the project, aligned to start on a Monday. */
function buildColumns(dates: IsoDate[]): DayColumn[] {
  if (dates.length === 0) return []

  const times = dates.map((iso) => parseIso(iso).getTime())
  let first = new Date(Math.min(...times))
  const lastDate = new Date(Math.max(...times))

  // Snap the left edge to Monday so a week is always exactly five columns and
  // the separator rhythm never drifts.
  while (first.getDay() !== 1) first = addDays(first, -1)

  let last = lastDate
  let added = 0
  while (added < TRAILING_PADDING_DAYS) {
    last = addDays(last, 1)
    if (!isWeekend(last)) added += 1
  }
  // Fill out the final week so the last month header is not a stub.
  while (last.getDay() !== 5) last = addDays(last, 1)

  return eachWorkday(toIso(first), toIso(last)).map((date) => ({
    iso: toIso(date),
    date,
    dayOfMonth: date.getDate(),
    monthIndex: date.getMonth(),
    weekday: weekdayShort(date),
    isWeekStart: date.getDay() === 1,
  }))
}

function groupByMonth(days: DayColumn[]): HeaderGroup[] {
  const groups: HeaderGroup[] = []
  let previousYear: number | null = null

  days.forEach((day, index) => {
    const year = day.date.getFullYear()
    const last = groups[groups.length - 1]
    const key = `${year}-${day.monthIndex}`

    if (last && last.key === key) {
      last.span += 1
      return
    }

    // The year is only repeated when it actually changes — less noise.
    const showYear = previousYear === null || previousYear !== year
    previousYear = year
    groups.push({
      key,
      label: showYear
        ? `${monthNameNominative(day.monthIndex)} ${year}`
        : monthNameNominative(day.monthIndex),
      startIndex: index,
      span: 1,
    })
  })

  return groups
}

function buildLinks(
  project: Project,
  changeSet: ChangeSet | null,
  rowById: Map<string, GanttRow>,
): GanttLink[] {
  const kindByEdge = new Map<string, LinkKind>()
  for (const link of changeSet?.links ?? []) {
    kindByEdge.set(`${link.sourceId}->${link.targetId}`, link.kind)
  }

  const links: GanttLink[] = []

  for (const task of project.tasks) {
    for (const sourceId of task.predecessor_ids) {
      if (!rowById.has(sourceId)) continue
      const edge = `${sourceId}->${task.id}`
      links.push({
        id: edge,
        sourceId,
        targetId: task.id,
        kind: kindByEdge.get(edge) === 'added' ? 'added' : 'normal',
      })
    }
  }

  // Removed edges are not in the current project, but both endpoints still
  // exist — drawing them as dashed ghosts is what makes a rewiring visible.
  for (const link of changeSet?.links ?? []) {
    if (link.kind !== 'removed') continue
    if (!rowById.has(link.sourceId) || !rowById.has(link.targetId)) continue
    links.push({
      id: `removed:${link.sourceId}->${link.targetId}`,
      sourceId: link.sourceId,
      targetId: link.targetId,
      kind: 'removed',
    })
  }

  return links
}

/** Counts per change type, for the legend above the chart. */
export function changeCounts(changeSet: ChangeSet | null): Record<ChangeType, number> {
  const counts: Record<ChangeType, number> = { direct: 0, created: 0, derived: 0 }
  if (!changeSet) return counts
  for (const type of Object.values(changeSet.byTask)) counts[type] += 1
  return counts
}

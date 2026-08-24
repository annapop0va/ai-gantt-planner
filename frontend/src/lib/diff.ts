import type {
  ChangeSet,
  ChangeType,
  CreatedTaskChange,
  DerivedTaskChange,
  FieldDelta,
  LinkChange,
  ModifiedTaskChange,
  Project,
  ReleaseImpact,
  Task,
} from '@/types/project'
import { formatDayMonthLong, parseIso, workdaysBetween } from './date'

/**
 * Derives the AI change set by diffing two Project DTOs.
 *
 * Why diff instead of hardcoding the demo numbers: the summary, the Gantt
 * highlighting and the release-impact block then all read from one computed
 * object. When the real backend starts returning its own diff payload
 * (`direct_changes` / `created_tasks` / `derived_schedule_changes`), only this
 * file is replaced — every consumer keeps working.
 *
 * Classification, in precedence order (technical-blueprint §6):
 *   created — the task did not exist before.
 *   direct  — an input field the user can command changed: duration, effort,
 *             assignee, name, description, or the predecessor set.
 *   derived — only the scheduled dates moved, as a consequence of something
 *             else. This is the quietest category by design.
 */
export function computeChangeSet(before: Project, after: Project): ChangeSet {
  const beforeById = new Map(before.tasks.map((t) => [t.id, t]))
  const afterById = new Map(after.tasks.map((t) => [t.id, t]))
  const nameOf = (id: string) => afterById.get(id)?.name ?? beforeById.get(id)?.name ?? id

  const byTask: Record<string, ChangeType> = {}
  const modified: ModifiedTaskChange[] = []
  const created: CreatedTaskChange[] = []
  const derived: DerivedTaskChange[] = []
  const previousSchedule: ChangeSet['previousSchedule'] = {}

  const ordered = [...after.tasks].sort((a, b) => a.display_order - b.display_order)

  for (const task of ordered) {
    const prev = beforeById.get(task.id)

    if (!prev) {
      byTask[task.id] = 'created'
      created.push({
        taskId: task.id,
        name: task.name,
        assignee: task.assignee,
        durationWorkdays: task.duration_workdays,
        plannedEffortHours: task.planned_effort_hours,
      })
      continue
    }

    if (prev.start_date !== task.start_date || prev.end_date !== task.end_date) {
      previousSchedule[task.id] = { start: prev.start_date, end: prev.end_date }
    }

    const deltas = fieldDeltas(prev, task, nameOf)

    if (deltas.length > 0) {
      byTask[task.id] = 'direct'
      modified.push({ taskId: task.id, name: task.name, deltas })
      continue
    }

    if (prev.start_date !== task.start_date || prev.end_date !== task.end_date) {
      byTask[task.id] = 'derived'
      derived.push({
        taskId: task.id,
        name: task.name,
        beforeStart: prev.start_date,
        afterStart: task.start_date,
        beforeEnd: prev.end_date,
        afterEnd: task.end_date,
        workdayShift: workdaysBetween(prev.end_date, task.end_date),
      })
    }
  }

  return {
    fromRevision: before.revision,
    toRevision: after.revision,
    byTask,
    modified,
    created,
    derived,
    links: linkChanges(before, after),
    previousSchedule,
    release: releaseImpact(before, after),
    taskCountBefore: before.tasks.length,
    taskCountAfter: after.tasks.length,
  }
}

/** Human-readable before/after pairs for every commandable field that moved. */
function fieldDeltas(prev: Task, next: Task, nameOf: (id: string) => string): FieldDelta[] {
  const deltas: FieldDelta[] = []

  if (prev.duration_workdays !== next.duration_workdays) {
    deltas.push({
      label: 'Длительность',
      before: `${prev.duration_workdays} дн.`,
      after: `${next.duration_workdays} дн.`,
    })
    // Effort is derived from duration, but PMs plan against hours, so the
    // summary always shows both rather than making them do ×8 in their head.
    deltas.push({
      label: 'Трудоёмкость',
      before: `${prev.planned_effort_hours} ч`,
      after: `${next.planned_effort_hours} ч`,
    })
  } else if (prev.planned_effort_hours !== next.planned_effort_hours) {
    deltas.push({
      label: 'Трудоёмкость',
      before: `${prev.planned_effort_hours} ч`,
      after: `${next.planned_effort_hours} ч`,
    })
  }

  if (prev.assignee !== next.assignee) {
    deltas.push({
      label: 'Исполнитель',
      before: prev.assignee ?? 'не назначен',
      after: next.assignee ?? 'не назначен',
    })
  }

  if (prev.name !== next.name) {
    deltas.push({ label: 'Название', before: prev.name, after: next.name })
  }

  if (prev.description !== next.description) {
    deltas.push({ label: 'Описание', before: prev.description, after: next.description })
  }

  if (!sameIdSet(prev.predecessor_ids, next.predecessor_ids)) {
    deltas.push({
      label: 'Предшественники',
      before: prev.predecessor_ids.map(nameOf).join(', ') || 'нет',
      after: next.predecessor_ids.map(nameOf).join(', ') || 'нет',
    })
  }

  if (prev.start_not_before !== next.start_not_before) {
    deltas.push({
      label: 'Не ранее',
      before: prev.start_not_before ? formatDayMonthLong(prev.start_not_before) : 'нет',
      after: next.start_not_before ? formatDayMonthLong(next.start_not_before) : 'нет',
    })
  }

  return deltas
}

function sameIdSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false
  const set = new Set(a)
  return b.every((id) => set.has(id))
}

/**
 * Dependency edges added or removed by the change set. Rendering both — the new
 * arrow solid, the removed one as a dashed ghost — is what makes a rewiring
 * like "QA now waits for both fix tasks" legible on the chart itself.
 */
function linkChanges(before: Project, after: Project): LinkChange[] {
  const edgeKey = (source: string, target: string) => `${source}->${target}`

  const beforeEdges = new Set<string>()
  for (const task of before.tasks) {
    for (const p of task.predecessor_ids) beforeEdges.add(edgeKey(p, task.id))
  }

  const afterEdges = new Set<string>()
  for (const task of after.tasks) {
    for (const p of task.predecessor_ids) afterEdges.add(edgeKey(p, task.id))
  }

  const afterTaskIds = new Set(after.tasks.map((t) => t.id))
  const changes: LinkChange[] = []

  for (const edge of afterEdges) {
    if (!beforeEdges.has(edge)) {
      const [sourceId, targetId] = edge.split('->')
      changes.push({ sourceId, targetId, kind: 'added' })
    }
  }

  for (const edge of beforeEdges) {
    if (afterEdges.has(edge)) continue
    const [sourceId, targetId] = edge.split('->')
    // A removed edge is only drawable if both endpoints still exist.
    if (afterTaskIds.has(sourceId) && afterTaskIds.has(targetId)) {
      changes.push({ sourceId, targetId, kind: 'removed' })
    }
  }

  return changes
}

/** The project's release = the task that finishes last. */
export function lastTask(project: Project): Task | null {
  if (project.tasks.length === 0) return null
  return project.tasks.reduce((latest, task) =>
    parseIso(task.end_date) > parseIso(latest.end_date) ? task : latest,
  )
}

export function releaseDate(project: Project): string | null {
  return lastTask(project)?.end_date ?? null
}

function releaseImpact(before: Project, after: Project): ReleaseImpact | null {
  const beforeLast = lastTask(before)
  const afterLast = lastTask(after)
  if (!beforeLast || !afterLast) return null
  if (beforeLast.end_date === afterLast.end_date) return null

  return {
    taskId: afterLast.id,
    taskName: afterLast.name,
    beforeDate: beforeLast.end_date,
    afterDate: afterLast.end_date,
    workdayShift: workdaysBetween(beforeLast.end_date, afterLast.end_date),
  }
}

/** Distinct assignees, for the "5 исполнителей" metric. */
export function assigneeCount(project: Project): number {
  return new Set(project.tasks.map((t) => t.assignee).filter(Boolean)).size
}

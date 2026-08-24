/**
 * Converts the backend's own diff (`BackendChangeSummary` — direct_changes /
 * created_tasks / dependency_changes / derived_schedule_changes, see
 * @/api/chat) into the frontend's `ChangeSet` view model that `GanttView` and
 * `ChangeSummary` already know how to render.
 *
 * Deliberately independent of `@/lib/diff.ts::computeChangeSet` — that
 * function *re-derives* a diff by comparing two full snapshots, which is the
 * right approach for the mock demo (no backend diff exists there) but wrong
 * here: the backend already computed the authoritative classification
 * (direct/created/derived, precedence and all), and re-deriving our own from
 * the same before/after snapshots could disagree with it. This file only
 * *adapts* field names and adds the two things the backend response doesn't
 * carry — a release-date comparison and predecessor UUIDs resolved to names —
 * both pure presentation, using dates/names the backend already computed.
 */

import { lastTask, releaseDate } from '@/lib/diff'
import { formatDayMonthLong, workdaysBetween } from '@/lib/date'
import type { BackendChangeSummary, BackendFieldDelta } from '@/api/chat'
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
} from '@/types/project'

/** Mirrors the backend's public HOURS_PER_WORKDAY constant (product-spec §5) —
 * a fixed unit conversion for display, not a scheduling calculation. */
const HOURS_PER_WORKDAY = 8

const FIELD_LABELS: Record<string, string> = {
  name: 'Название',
  description: 'Описание',
  assignee: 'Исполнитель',
  duration_workdays: 'Длительность',
  predecessor_ids: 'Предшественники',
  start_not_before: 'Не ранее',
}

export function adaptServerChangeSummary(
  summary: BackendChangeSummary,
  previousProject: Project,
  nextProject: Project,
): ChangeSet {
  const nameOf = buildNameResolver(previousProject, nextProject)
  const byTask: Record<string, ChangeType> = {}

  const modified: ModifiedTaskChange[] = summary.direct_changes.map((change) => {
    byTask[change.task_id] = 'direct'
    return {
      taskId: change.task_id,
      name: change.name,
      deltas: change.deltas.flatMap((delta) => formatFieldDelta(delta, nameOf)),
    }
  })

  const created: CreatedTaskChange[] = summary.created_tasks.map((task) => {
    byTask[task.task_id] = 'created'
    return {
      taskId: task.task_id,
      name: task.name,
      assignee: task.assignee,
      durationWorkdays: task.duration_workdays,
      plannedEffortHours: task.planned_effort_hours,
    }
  })

  const derived: DerivedTaskChange[] = summary.derived_schedule_changes.map((change) => {
    if (!(change.task_id in byTask)) byTask[change.task_id] = 'derived'
    return {
      taskId: change.task_id,
      name: change.name,
      beforeStart: change.before_start,
      afterStart: change.after_start,
      beforeEnd: change.before_end,
      afterEnd: change.after_end,
      workdayShift: change.workday_shift,
    }
  })

  const links: LinkChange[] = summary.dependency_changes.map((change) => ({
    sourceId: change.predecessor_id,
    targetId: change.successor_id,
    kind: change.kind,
  }))

  const previousSchedule: ChangeSet['previousSchedule'] = {}
  for (const change of summary.derived_schedule_changes) {
    previousSchedule[change.task_id] = { start: change.before_start, end: change.before_end }
  }

  return {
    fromRevision: summary.previous_revision,
    toRevision: summary.new_revision,
    byTask,
    modified,
    created,
    derived,
    links,
    previousSchedule,
    release: computeReleaseImpact(previousProject, nextProject),
    taskCountBefore: previousProject.tasks.length,
    taskCountAfter: nextProject.tasks.length,
  }
}

function buildNameResolver(previousProject: Project, nextProject: Project): (id: string) => string {
  const byId = new Map<string, string>()
  for (const task of previousProject.tasks) byId.set(task.id, task.name)
  for (const task of nextProject.tasks) byId.set(task.id, task.name)
  return (id: string) => byId.get(id) ?? id
}

function formatFieldDelta(delta: BackendFieldDelta, nameOf: (id: string) => string): FieldDelta[] {
  if (delta.field === 'duration_workdays') {
    const beforeWorkdays = Number(delta.before)
    const afterWorkdays = Number(delta.after)
    return [
      { label: 'Длительность', before: `${delta.before} дн.`, after: `${delta.after} дн.` },
      {
        label: 'Трудоёмкость',
        before: `${beforeWorkdays * HOURS_PER_WORKDAY} ч`,
        after: `${afterWorkdays * HOURS_PER_WORKDAY} ч`,
      },
    ]
  }

  if (delta.field === 'start_not_before') {
    return [
      {
        label: 'Не ранее',
        before: delta.before ? formatDayMonthLong(delta.before) : 'нет',
        after: delta.after ? formatDayMonthLong(delta.after) : 'нет',
      },
    ]
  }

  if (delta.field === 'predecessor_ids') {
    const resolve = (raw: string) => (raw ? raw.split(',').map(nameOf).join(', ') : 'нет')
    return [{ label: 'Предшественники', before: resolve(delta.before), after: resolve(delta.after) }]
  }

  return [{ label: FIELD_LABELS[delta.field] ?? delta.field, before: delta.before, after: delta.after }]
}

function computeReleaseImpact(previousProject: Project, nextProject: Project): ReleaseImpact | null {
  const beforeDate = releaseDate(previousProject)
  const afterDate = releaseDate(nextProject)
  if (!beforeDate || !afterDate || beforeDate === afterDate) return null

  const afterLast = lastTask(nextProject)
  return {
    taskId: afterLast?.id ?? '',
    taskName: afterLast?.name ?? '',
    beforeDate,
    afterDate,
    workdayShift: workdaysBetween(beforeDate, afterDate),
  }
}

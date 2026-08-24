/**
 * Frontend mirror of the backend Project DTO (docs/product-spec.md §6).
 *
 * The frontend never computes dates, working days, successors or effort — those
 * arrive already resolved from the backend. Keeping this type identical to the
 * DTO means the prototype's fixtures can later be swapped for real API
 * responses without touching any component.
 */

export type CreatedSource = 'import' | 'agent'

/** ISO date, `YYYY-MM-DD`. Date-only, no timezone. */
export type IsoDate = string

export interface Task {
  id: string
  name: string
  description: string
  assignee: string | null
  duration_workdays: number
  planned_effort_hours: number
  predecessor_ids: string[]
  /** Derived server-side; present on the DTO, never recomputed here. */
  successor_ids: string[]
  start_not_before: IsoDate | null
  start_date: IsoDate
  end_date: IsoDate
  display_order: number
  created_source: CreatedSource
}

export interface Project {
  id: string
  name: string
  project_start_date: IsoDate
  revision: number
  tasks: Task[]
  created_at: string
  updated_at: string
}

/* -----------------------------------------------------------------------------
 * AI change semantics
 * -------------------------------------------------------------------------- */

/**
 * How a task was touched by the last AI command.
 *
 * Precedence when a task qualifies for more than one (technical-blueprint §6):
 *   created > direct > derived
 */
export type ChangeType = 'direct' | 'created' | 'derived'

/** A single field-level difference shown in the change summary. */
export interface FieldDelta {
  label: string
  before: string
  after: string
}

export interface ModifiedTaskChange {
  taskId: string
  name: string
  deltas: FieldDelta[]
}

export interface CreatedTaskChange {
  taskId: string
  name: string
  assignee: string | null
  durationWorkdays: number
  plannedEffortHours: number
}

export interface DerivedTaskChange {
  taskId: string
  name: string
  beforeStart: IsoDate
  afterStart: IsoDate
  beforeEnd: IsoDate
  afterEnd: IsoDate
  /** Shift of the end date, in working days. Positive = later. */
  workdayShift: number
}

/** A dependency edge that the change set added or removed. */
export interface LinkChange {
  sourceId: string
  targetId: string
  kind: 'added' | 'removed'
}

export interface ReleaseImpact {
  taskId: string
  taskName: string
  beforeDate: IsoDate
  afterDate: IsoDate
  /** Working days between the two release dates. Positive = slipped. */
  workdayShift: number
}

/**
 * The full diff between two project revisions. Produced by `computeChangeSet`
 * from before/after DTOs, so it stays correct if the backend ever returns a
 * different result than the canonical demo.
 */
export interface ChangeSet {
  fromRevision: number
  toRevision: number
  /** Change type per task id — the index the Gantt reads for highlighting. */
  byTask: Record<string, ChangeType>
  modified: ModifiedTaskChange[]
  created: CreatedTaskChange[]
  derived: DerivedTaskChange[]
  links: LinkChange[]
  /** Previous bar position per task, for the "was here" ghost outline. */
  previousSchedule: Record<string, { start: IsoDate; end: IsoDate }>
  release: ReleaseImpact | null
  taskCountBefore: number
  taskCountAfter: number
}

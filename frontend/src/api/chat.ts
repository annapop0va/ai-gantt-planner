import { apiRequest } from './client'
import type { Project } from '@/types/project'

export interface BackendFieldDelta {
  field: string
  before: string
  after: string
}

export interface BackendDirectChange {
  task_id: string
  name: string
  deltas: BackendFieldDelta[]
}

export interface BackendCreatedTaskChange {
  task_id: string
  name: string
  assignee: string | null
  duration_workdays: number
  planned_effort_hours: number
}

export interface BackendDependencyChange {
  predecessor_id: string
  successor_id: string
  kind: 'added' | 'removed'
}

export interface BackendDerivedScheduleChange {
  task_id: string
  name: string
  before_start: string
  after_start: string
  before_end: string
  after_end: string
  workday_shift: number
}

/** Mirrors `app.domain.diff.ChangeSummary` — the backend's own diff shape,
 * deliberately distinct from the frontend's mock-only `ChangeSet`
 * (see @/app/serverChangeSummaryAdapter, which converts one into the other). */
export interface BackendChangeSummary {
  previous_revision: number
  new_revision: number
  direct_changes: BackendDirectChange[]
  created_tasks: BackendCreatedTaskChange[]
  dependency_changes: BackendDependencyChange[]
  derived_schedule_changes: BackendDerivedScheduleChange[]
}

export type ChatStatus = 'applied' | 'clarification_required' | 'rejected'

export interface ChatResult {
  status: ChatStatus
  message: string
  project: Project | null
  change_summary: BackendChangeSummary | null
  warnings: string[]
}

export async function sendChatMessage(
  projectId: string,
  message: string,
  expectedRevision: number,
): Promise<ChatResult> {
  return apiRequest<ChatResult>(`/api/v1/projects/${projectId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, expected_revision: expectedRevision }),
  })
}

export type Screen = 'import' | 'importLoading' | 'importError' | 'workspace'

export type ExportStatus = 'idle' | 'preparing' | 'done'

/** Display name for the canonical demo project — the fixture's `name` field is a technical slug. */
export const PROJECT_DISPLAY_NAME = 'Карточка пациента'

/**
 * The 12 UI states the take-home brief asks to be reachable for review. Every
 * one is also reachable through the real interaction that produces it — this
 * list only makes them reachable in one click for grading.
 */
export type DevState =
  | 'import'
  | 'importLoading'
  | 'importError'
  | 'workspaceBeforeAi'
  | 'aiProcessing'
  | 'aiSuccess'
  | 'clarification'
  | 'rejected'
  | 'technicalError'
  | 'taskModal'
  | 'uploadConfirmation'
  | 'exportSuccess'

export const DEV_STATE_LABELS: Record<DevState, string> = {
  import: 'Import',
  importLoading: 'Import loading',
  importError: 'Import error',
  workspaceBeforeAi: 'Workspace before AI',
  aiProcessing: 'AI processing',
  aiSuccess: 'AI success',
  clarification: 'Clarification',
  rejected: 'Rejected',
  technicalError: 'Technical error',
  taskModal: 'Task modal',
  uploadConfirmation: 'Upload confirmation',
  exportSuccess: 'Export success',
}

export const DEV_STATE_ORDER: DevState[] = [
  'import',
  'importLoading',
  'importError',
  'workspaceBeforeAi',
  'aiProcessing',
  'aiSuccess',
  'clarification',
  'rejected',
  'technicalError',
  'taskModal',
  'uploadConfirmation',
  'exportSuccess',
]

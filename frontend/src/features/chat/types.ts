import type { ChangeSet } from '@/types/project'

export type ChatStatus = 'idle' | 'processing'

export type ChatTurn =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; kind: 'success'; text: string; changeSet: ChangeSet }
  | { id: string; role: 'assistant'; kind: 'clarification'; text: string }
  | { id: string; role: 'assistant'; kind: 'rejected'; text: string; relatedTaskId: string | null }
  | { id: string; role: 'assistant'; kind: 'error'; text: string }
  /** Server mode, before MCP + OpenRouter are wired up (see docs/backend-contract-audit.md). */
  | { id: string; role: 'assistant'; kind: 'disabled'; text: string }

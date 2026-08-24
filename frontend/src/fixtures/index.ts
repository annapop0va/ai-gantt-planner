import before from '@fixtures/mock_project_before.json'
import after from '@fixtures/mock_project_after.json'
import type { Project } from '@/types/project'

/**
 * Fixture adapter.
 *
 * The canonical demo data lives once, at the repository root, shared with
 * backend and QA. Vite aliases `@fixtures` to it (see vite.config.ts) so
 * nothing is duplicated or hand-transcribed. The `as unknown as Project` cast
 * is the single place where untyped JSON becomes a typed DTO — the same seam
 * the real API client will occupy later.
 */
export const projectBefore = before as unknown as Project
export const projectAfter = after as unknown as Project

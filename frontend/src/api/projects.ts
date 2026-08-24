/**
 * Server-mode calls. The dev `/changes` endpoint deliberately has no client
 * here — production chat never calls it (see app/App.tsx), and it exists
 * only for backend curl/pytest verification.
 */

import { apiRequest, apiRequestBlob } from './client'
import type { Project } from '@/types/project'

export interface ImportResult {
  project: Project
  warnings: string[]
}

export async function importProject(file: File, projectStartDate: string): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('project_start_date', projectStartDate)
  return apiRequest<ImportResult>('/api/v1/projects/import', { method: 'POST', body: formData })
}

export async function getProject(projectId: string): Promise<Project> {
  return apiRequest<Project>(`/api/v1/projects/${projectId}`)
}

export interface ExportResult {
  blob: Blob
  filename: string
}

export async function exportProject(projectId: string): Promise<ExportResult> {
  const { blob, filename } = await apiRequestBlob(`/api/v1/projects/${projectId}/export`)
  return { blob, filename: filename ?? 'project.xlsx' }
}

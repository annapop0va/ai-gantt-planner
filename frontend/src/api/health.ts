import { apiRequest } from './client'

/**
 * `GET /api/v1/health`, bounded by `timeoutMs`. Never throws — a sleeping/
 * unreachable backend, a timeout, and a non-2xx response are all just "not
 * ready yet" here. Read-only: safe to call as many times as needed.
 */
export async function checkHealth(timeoutMs: number): Promise<boolean> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    await apiRequest('/api/v1/health', { signal: controller.signal })
    return true
  } catch {
    return false
  } finally {
    window.clearTimeout(timeout)
  }
}

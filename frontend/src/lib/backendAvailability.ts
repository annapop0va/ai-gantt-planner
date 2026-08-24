/**
 * Cold-start policy for a free-tier backend that may be asleep: sequential
 * (never parallel) health-check attempts within a fixed time budget, with
 * backoff between attempts. Pure and dependency-injected (no fetch/DOM
 * reference except through the optional defaults) so it can be exercised
 * deterministically without a real network or real timers (inject a fake
 * `checkHealth`/`sleep`/`now`).
 *
 * Only ever wraps a read-only check (health, and optionally a GET restore).
 * Never wrap a mutation (POST /chat, import, ChangeSet) in this — a retried
 * mutation could apply twice.
 */

export type BackendAvailabilityResult = 'ready' | 'unavailable'

export interface WaitForBackendOptions {
  /** One health-check attempt. Must resolve to a boolean, never throw. */
  checkHealth: () => Promise<boolean>
  /** Total wall-clock budget across all attempts and delays. */
  budgetMs?: number
  /** Delay before each successive retry. The last entry repeats if more
   * attempts fit in the budget than entries provided. */
  backoffScheduleMs?: number[]
  sleep?: (ms: number) => Promise<void>
  now?: () => number
}

export const DEFAULT_BUDGET_MS = 90_000
export const DEFAULT_BACKOFF_SCHEDULE_MS = [1_500, 2_500, 4_000, 6_000, 9_000, 9_000]

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

/**
 * Awaits `checkHealth()` once; if it fails, sleeps per the backoff schedule
 * and tries again, stopping the moment the elapsed time would exceed
 * `budgetMs` — never an unbounded loop. Attempts are strictly sequential:
 * the next one is never started before the previous settles.
 */
export async function waitForBackend(options: WaitForBackendOptions): Promise<BackendAvailabilityResult> {
  const {
    checkHealth,
    budgetMs = DEFAULT_BUDGET_MS,
    backoffScheduleMs = DEFAULT_BACKOFF_SCHEDULE_MS,
    sleep = defaultSleep,
    now = () => Date.now(),
  } = options

  const start = now()
  let attempt = 0

  for (;;) {
    const ok = await checkHealth()
    if (ok) return 'ready'

    const elapsed = now() - start
    if (elapsed >= budgetMs) return 'unavailable'

    const delay = backoffScheduleMs[Math.min(attempt, backoffScheduleMs.length - 1)]
    if (elapsed + delay >= budgetMs) return 'unavailable'

    attempt += 1
    await sleep(delay)
  }
}

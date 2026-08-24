import { Loader2 } from 'lucide-react'
import styles from './ServerStartingScreen.module.css'

/**
 * Shown instead of the Import screen while the cold-start health-check
 * (app/App.tsx's boot effect, backed by @/lib/backendAvailability) is still
 * waiting for a free-tier backend to wake up. Deliberately has no Render/
 * OpenRouter/MCP terminology and no fake progress bar — just an honest wait.
 */
export function ServerStartingScreen() {
  return (
    <div className={styles.page}>
      <div className={styles.card} role="status" aria-live="polite">
        <span className={styles.spinner} aria-hidden>
          <Loader2 size={28} />
        </span>
        <h1 className={styles.title}>Запускаем сервер…</h1>
        <p className={styles.subtitle}>Подготавливаем сервер… Первый запуск может занять до минуты.</p>
      </div>
    </div>
  )
}

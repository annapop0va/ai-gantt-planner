import { useEffect, useState } from 'react'
import { CheckCircle2, Circle } from 'lucide-react'
import styles from './ImportLoadingScreen.module.css'
import { cx } from '@/lib/cx'

const STEPS = ['Файл загружен', 'Проверяем данные', 'Рассчитываем расписание', 'Строим диаграмму']

const STEP_DELAY_MS = 480

export interface ImportLoadingScreenProps {
  onDone: () => void
}

/**
 * Sequenced checklist, no fake percentage (product-spec's explicit instruction).
 * "Файл загружен" starts already complete — the upload itself finished on the
 * previous screen — and the remaining steps complete one at a time.
 */
export function ImportLoadingScreen({ onDone }: ImportLoadingScreenProps) {
  const [doneCount, setDoneCount] = useState(1)

  useEffect(() => {
    if (doneCount >= STEPS.length) {
      const timeout = window.setTimeout(onDone, STEP_DELAY_MS)
      return () => window.clearTimeout(timeout)
    }
    const timeout = window.setTimeout(() => setDoneCount((c) => c + 1), STEP_DELAY_MS)
    return () => window.clearTimeout(timeout)
  }, [doneCount, onDone])

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <h1 className={styles.title}>Строим план проекта</h1>
        <p className={styles.subtitle}>Это займёт несколько секунд</p>
        <div className={styles.steps}>
          {STEPS.map((label, index) => {
            const done = index < doneCount
            const active = index === doneCount
            return (
              <div
                key={label}
                className={cx(styles.step, done && styles.stepDone, active && styles.stepActive)}
              >
                <span
                  className={cx(
                    styles.glyph,
                    done && styles.glyphDone,
                    active && styles.glyphActive,
                    !done && !active && styles.glyphPending,
                  )}
                >
                  {done ? (
                    <CheckCircle2 size={18} />
                  ) : active ? (
                    <span className={styles.pulseDot} />
                  ) : (
                    <Circle size={18} />
                  )}
                </span>
                {label}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

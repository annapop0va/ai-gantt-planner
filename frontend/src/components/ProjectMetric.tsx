import type { ReactNode } from 'react'
import { ArrowRight } from 'lucide-react'
import styles from './ProjectMetric.module.css'
import { cx } from '@/lib/cx'

export interface ProjectMetricProps {
  label: string
  value: ReactNode
  icon?: ReactNode
  /** When present, renders `previous → value` with the old value struck out. */
  previousValue?: ReactNode
  /** Short delta pill, e.g. `+5 рабочих дней`. */
  delta?: string
  emphasis?: boolean
}

export function ProjectMetric({
  label,
  value,
  icon,
  previousValue,
  delta,
  emphasis,
}: ProjectMetricProps) {
  return (
    <div className={cx(styles.metric, emphasis && styles.changed)}>
      {icon ? (
        <span className={styles.glyph} aria-hidden>
          {icon}
        </span>
      ) : null}
      <div className={styles.text}>
        <span className={styles.label}>{label}</span>
        <span className={styles.valueRow}>
          {previousValue ? (
            <>
              <span className={styles.previous}>{previousValue}</span>
              <ArrowRight size={11} className={styles.arrow} aria-hidden />
            </>
          ) : null}
          <span className={styles.value}>{value}</span>
          {delta ? <span className={styles.delta}>{delta}</span> : null}
        </span>
      </div>
    </div>
  )
}

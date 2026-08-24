import { ArrowLeft, ArrowRight } from 'lucide-react'
import styles from './TaskChip.module.css'
import { Tooltip } from './Tooltip'
import { cx } from '@/lib/cx'

export interface TaskChipProps {
  name: string
  /** Which side of the dependency this task sits on. */
  direction: 'predecessor' | 'successor'
  highlight?: boolean
  onClick?: () => void
}

/**
 * A related task, shown by name rather than by UUID. Clicking navigates the
 * task modal to that task, so a PM can walk a dependency chain without closing
 * the dialog.
 */
export function TaskChip({ name, direction, highlight, onClick }: TaskChipProps) {
  return (
    <Tooltip content={name}>
      <button
        type="button"
        className={cx(styles.chip, highlight && styles.created)}
        onClick={onClick}
      >
        <span className={styles.glyph} aria-hidden>
          {direction === 'predecessor' ? <ArrowLeft size={11} /> : <ArrowRight size={11} />}
        </span>
        <span className={styles.label}>{name}</span>
      </button>
    </Tooltip>
  )
}

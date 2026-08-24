import { useState } from 'react'
import { TerminalSquare, X } from 'lucide-react'
import styles from './DevStateSwitcher.module.css'
import { DEV_STATE_LABELS, DEV_STATE_ORDER } from './types'
import type { DevState } from './types'
import { cx } from '@/lib/cx'

export interface DevStateSwitcherProps {
  onJump: (state: DevState) => void
}

/**
 * Dev-only affordance for jumping straight to any of the 12 required UI
 * states. Deliberately styled nothing like the product (dark, dashed,
 * monospace, fixed-position) so it reads as tooling, not a feature.
 */
export function DevStateSwitcher({ onJump }: DevStateSwitcherProps) {
  const [open, setOpen] = useState(false)
  const [lastJumped, setLastJumped] = useState<DevState | null>(null)

  return (
    <div className={styles.root}>
      {open ? (
        <div className={styles.panel} role="dialog" aria-label="Dev state switcher">
          <div className={styles.panelHead}>
            <span className={styles.panelTitle}>Dev · UI states</span>
            <button className={styles.close} type="button" onClick={() => setOpen(false)} aria-label="Закрыть">
              <X size={13} />
            </button>
          </div>
          <div className={styles.list}>
            {DEV_STATE_ORDER.map((state, index) => (
              <button
                key={state}
                type="button"
                className={cx(styles.item, state === lastJumped && styles.itemActive)}
                onClick={() => {
                  setLastJumped(state)
                  onJump(state)
                }}
              >
                <span className={styles.itemNumber}>{String(index + 1).padStart(2, '0')}</span>
                {DEV_STATE_LABELS[state]}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <button type="button" className={styles.toggle} onClick={() => setOpen((v) => !v)}>
        <TerminalSquare size={13} />
        DEV
      </button>
    </div>
  )
}

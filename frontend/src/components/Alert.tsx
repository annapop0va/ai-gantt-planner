import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import styles from './Alert.module.css'
import { cx } from '@/lib/cx'

export type AlertTone = 'info' | 'warning' | 'error' | 'success' | 'neutral'

export interface AlertProps {
  tone?: AlertTone
  title?: ReactNode
  children?: ReactNode
  actions?: ReactNode
  icon?: ReactNode
  className?: string
}

const DEFAULT_ICONS: Record<AlertTone, ReactNode> = {
  info: <Info size={15} />,
  warning: <AlertTriangle size={15} />,
  error: <XCircle size={15} />,
  success: <CheckCircle2 size={15} />,
  neutral: <Info size={15} />,
}

export function Alert({
  tone = 'info',
  title,
  children,
  actions,
  icon,
  className,
}: AlertProps) {
  return (
    <div className={cx(styles.alert, styles[tone], className)} role="status">
      <span className={styles.glyph} aria-hidden>
        {icon ?? DEFAULT_ICONS[tone]}
      </span>
      <div className={styles.content}>
        {title ? <span className={styles.title}>{title}</span> : null}
        {children ? <div className={styles.description}>{children}</div> : null}
        {actions ? <div className={styles.actions}>{actions}</div> : null}
      </div>
    </div>
  )
}

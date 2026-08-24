import type { HTMLAttributes, ReactNode } from 'react'
import styles from './Badge.module.css'
import { cx } from '@/lib/cx'

export type BadgeTone =
  | 'neutral'
  | 'accent'
  | 'direct'
  | 'created'
  | 'derived'
  | 'success'
  | 'warning'
  | 'error'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  icon?: ReactNode
  children: ReactNode
}

export function Badge({ tone = 'neutral', icon, className, children, ...rest }: BadgeProps) {
  return (
    <span className={cx(styles.badge, styles[tone], className)} {...rest}>
      {icon}
      {children}
    </span>
  )
}

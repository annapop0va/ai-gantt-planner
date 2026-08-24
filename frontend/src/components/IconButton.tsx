import type { ButtonHTMLAttributes, ReactNode } from 'react'
import styles from './IconButton.module.css'
import { cx } from '@/lib/cx'

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Required — icon-only controls have no visible text. */
  label: string
  icon: ReactNode
  variant?: 'ghost' | 'outline' | 'accent'
  size?: 'sm' | 'md' | 'lg'
}

export function IconButton({
  label,
  icon,
  variant = 'ghost',
  size = 'md',
  className,
  type = 'button',
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={cx(styles.iconButton, styles[variant], styles[size], className)}
      {...rest}
    >
      {icon}
    </button>
  )
}

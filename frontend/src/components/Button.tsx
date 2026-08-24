import type { ButtonHTMLAttributes, ReactNode } from 'react'
import styles from './Button.module.css'
import { cx } from '@/lib/cx'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'link'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  /** Rendered before the label, at 14px. */
  iconLeft?: ReactNode
  iconRight?: ReactNode
  fullWidth?: boolean
}

export function Button({
  variant = 'secondary',
  size = 'md',
  iconLeft,
  iconRight,
  fullWidth,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        styles.button,
        styles[variant],
        variant !== 'link' && styles[size],
        fullWidth && styles.fullWidth,
        className,
      )}
      {...rest}
    >
      {iconLeft ? <span className={styles.icon}>{iconLeft}</span> : null}
      {children}
      {iconRight ? <span className={styles.icon}>{iconRight}</span> : null}
    </button>
  )
}

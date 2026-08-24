import { useId } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'
import { Calendar } from 'lucide-react'
import styles from './Field.module.css'
import { cx } from '@/lib/cx'

export interface DateInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
}

/**
 * Native date control with the browser glyph replaced by our own icon, so it
 * matches the rest of the form. The native picker stays fully functional.
 */
export function DateInput({ label, hint, error, className, id, ...rest }: DateInputProps) {
  const autoId = useId()
  const inputId = id ?? autoId

  return (
    <div className={styles.field}>
      {label ? (
        <label className={styles.label} htmlFor={inputId}>
          {label}
        </label>
      ) : null}
      <span className={styles.dateWrap}>
        <input
          id={inputId}
          type="date"
          className={cx(styles.control, Boolean(error) && styles.invalid, className)}
          aria-invalid={error ? true : undefined}
          {...rest}
        />
        <Calendar size={14} className={styles.dateIcon} aria-hidden />
      </span>
      {error ? <span className={styles.error}>{error}</span> : null}
      {!error && hint ? <span className={styles.hint}>{hint}</span> : null}
    </div>
  )
}

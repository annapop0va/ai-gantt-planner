import { useId } from 'react'
import type { TextareaHTMLAttributes, ReactNode, Ref } from 'react'
import styles from './Field.module.css'
import { cx } from '@/lib/cx'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
  textareaRef?: Ref<HTMLTextAreaElement>
}

export function Textarea({
  label,
  hint,
  error,
  className,
  id,
  textareaRef,
  ...rest
}: TextareaProps) {
  const autoId = useId()
  const fieldId = id ?? autoId

  return (
    <div className={styles.field}>
      {label ? (
        <label className={styles.label} htmlFor={fieldId}>
          {label}
        </label>
      ) : null}
      <textarea
        id={fieldId}
        ref={textareaRef}
        className={cx(styles.textarea, Boolean(error) && styles.invalid, className)}
        aria-invalid={error ? true : undefined}
        {...rest}
      />
      {error ? <span className={styles.error}>{error}</span> : null}
      {!error && hint ? <span className={styles.hint}>{hint}</span> : null}
    </div>
  )
}

import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import styles from './Modal.module.css'
import { IconButton } from './IconButton'
import { cx } from '@/lib/cx'

export interface ModalProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  subtitle?: ReactNode
  /** Rendered to the right of the title, before the close button. */
  headerAside?: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  bare?: boolean
  children: ReactNode
}

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  headerAside,
  footer,
  size = 'md',
  bare,
  children,
}: ModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)

    // Prevent the workspace behind the dialog from scrolling.
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    modalRef.current?.focus()

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className={styles.overlay}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        className={cx(styles.modal, styles[size])}
      >
        <header className={cx(styles.header, bare && styles.headerBare)}>
          <div className={styles.headerText}>
            <h2 className={styles.title}>{title}</h2>
            {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
          </div>
          {headerAside}
          <IconButton
            label="Закрыть"
            icon={<X size={15} />}
            onClick={onClose}
            className={styles.close}
          />
        </header>
        <div className={cx(styles.body, bare && styles.bodyFlush)}>{children}</div>
        {footer ? <footer className={styles.footer}>{footer}</footer> : null}
      </div>
    </div>,
    document.body,
  )
}

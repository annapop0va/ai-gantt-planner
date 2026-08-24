import { cloneElement, useCallback, useRef, useState } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import styles from './Tooltip.module.css'
import { cx } from '@/lib/cx'

interface Position {
  left: number
  top: number
}

export interface TooltipProps {
  content: ReactNode
  /** `rich` renders a light surface card — used for the Gantt task tooltip. */
  variant?: 'dark' | 'rich'
  placement?: 'top' | 'bottom'
  delay?: number
  disabled?: boolean
  /** Must accept a ref and mouse handlers. */
  children: ReactElement
}

const VIEWPORT_MARGIN = 8
const ANCHOR_GAP = 8

/**
 * Hover/focus tooltip rendered in a portal.
 *
 * A portal is necessary because the Gantt bars live inside a scrolling,
 * `overflow: hidden` container — an in-flow tooltip would be clipped by it.
 * Position is measured on open and flipped when it would leave the viewport.
 */
export function Tooltip({
  content,
  variant = 'dark',
  placement = 'top',
  delay = 120,
  disabled,
  children,
}: TooltipProps) {
  const anchorRef = useRef<HTMLElement | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const timerRef = useRef<number | null>(null)
  const [position, setPosition] = useState<Position | null>(null)

  const place = useCallback(() => {
    const anchor = anchorRef.current
    const tip = tooltipRef.current
    if (!anchor || !tip) return

    const a = anchor.getBoundingClientRect()
    const t = tip.getBoundingClientRect()

    let top =
      placement === 'top' ? a.top - t.height - ANCHOR_GAP : a.bottom + ANCHOR_GAP
    // Flip when the preferred side does not fit.
    if (placement === 'top' && top < VIEWPORT_MARGIN) top = a.bottom + ANCHOR_GAP
    if (placement === 'bottom' && top + t.height > window.innerHeight - VIEWPORT_MARGIN) {
      top = a.top - t.height - ANCHOR_GAP
    }

    let left = a.left + a.width / 2 - t.width / 2
    left = Math.min(
      Math.max(left, VIEWPORT_MARGIN),
      window.innerWidth - t.width - VIEWPORT_MARGIN,
    )

    setPosition({ left, top: Math.max(VIEWPORT_MARGIN, top) })
  }, [placement])

  const open = useCallback(() => {
    if (disabled) return
    if (timerRef.current) window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => {
      // Render off-screen first so the tooltip can be measured, then place it.
      setPosition({ left: -9999, top: -9999 })
      requestAnimationFrame(place)
    }, delay)
  }, [delay, disabled, place])

  const close = useCallback(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current)
    setPosition(null)
  }, [])

  const child = cloneElement(children, {
    ref: (node: HTMLElement | null) => {
      anchorRef.current = node
      const { ref } = children as unknown as { ref?: unknown }
      if (typeof ref === 'function') (ref as (n: HTMLElement | null) => void)(node)
      else if (ref && typeof ref === 'object') {
        ;(ref as { current: HTMLElement | null }).current = node
      }
    },
    onMouseEnter: open,
    onMouseLeave: close,
    onFocus: open,
    onBlur: close,
  } as Record<string, unknown>)

  return (
    <>
      {child}
      {position && !disabled
        ? createPortal(
            <div
              ref={tooltipRef}
              role="tooltip"
              className={cx(styles.tooltip, variant === 'rich' && styles.rich)}
              style={{ left: position.left, top: position.top }}
            >
              {content}
            </div>,
            document.body,
          )
        : null}
    </>
  )
}

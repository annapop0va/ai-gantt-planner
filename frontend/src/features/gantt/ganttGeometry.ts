/**
 * Pure geometry for the chart: column/row indices in, pixel paths out.
 * Kept free of React so the routing logic stays readable and testable.
 */

export interface GanttMetrics {
  dayWidth: number
  rowHeight: number
  barHeight: number
}

export interface Point {
  x: number
  y: number
}

/** Left edge of a bar, in px, inset so adjacent bars do not touch. */
export const BAR_INSET = 2

export function barLeft(startIndex: number, m: GanttMetrics): number {
  return startIndex * m.dayWidth + BAR_INSET
}

export function barWidth(span: number, m: GanttMetrics): number {
  return Math.max(6, span * m.dayWidth - BAR_INSET * 2)
}

export function rowCenterY(rowIndex: number, m: GanttMetrics): number {
  return rowIndex * m.rowHeight + m.rowHeight / 2
}

export function rowTop(rowIndex: number, m: GanttMetrics): number {
  return rowIndex * m.rowHeight
}

const ELBOW = 9
const ARROW_LENGTH = 5

/**
 * Orthogonal Finish-to-Start route from the right edge of the source bar to the
 * left edge of the target bar.
 *
 * Two cases:
 *   forward  — the target starts after the source ends: a simple Z with one
 *              vertical leg.
 *   backward — the target starts at or before the source ends (common with
 *              parallel branches). The route detours through the gutter just
 *              above/below the target row so it never runs along a bar.
 */
export function dependencyPoints(
  source: { startIndex: number; span: number; rowIndex: number },
  target: { startIndex: number; rowIndex: number },
  m: GanttMetrics,
): Point[] {
  const sx = barLeft(source.startIndex, m) + barWidth(source.span, m)
  const sy = rowCenterY(source.rowIndex, m)
  const ty = rowCenterY(target.rowIndex, m)
  const endX = barLeft(target.startIndex, m) - ARROW_LENGTH - 1

  const sameRow = Math.abs(ty - sy) < 0.5

  if (endX >= sx + ELBOW) {
    if (sameRow) return [{ x: sx, y: sy }, { x: endX, y: ty }]
    return [
      { x: sx, y: sy },
      { x: sx + ELBOW, y: sy },
      { x: sx + ELBOW, y: ty },
      { x: endX, y: ty },
    ]
  }

  const direction = sameRow ? -1 : Math.sign(ty - sy)
  const laneY = ty - direction * (m.rowHeight / 2)

  return [
    { x: sx, y: sy },
    { x: sx + ELBOW, y: sy },
    { x: sx + ELBOW, y: laneY },
    { x: endX - ELBOW, y: laneY },
    { x: endX - ELBOW, y: ty },
    { x: endX, y: ty },
  ]
}

/** Arrowhead triangle sitting at the left edge of the target bar. */
export function arrowHeadPath(target: { startIndex: number; rowIndex: number }, m: GanttMetrics): string {
  const x = barLeft(target.startIndex, m) - 1
  const y = rowCenterY(target.rowIndex, m)
  return `M ${x} ${y} L ${x - ARROW_LENGTH} ${y - 3.2} L ${x - ARROW_LENGTH} ${y + 3.2} Z`
}

/**
 * Polyline with rounded corners. The radius is clamped per-corner to half of
 * the shorter adjacent segment, so tight routes degrade to sharp corners
 * instead of producing self-intersecting curves.
 */
export function roundedPath(points: Point[], radius = 4): string {
  if (points.length < 2) return ''
  if (points.length === 2) {
    return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`
  }

  let d = `M ${points[0].x} ${points[0].y}`

  for (let i = 1; i < points.length - 1; i += 1) {
    const prev = points[i - 1]
    const curr = points[i]
    const next = points[i + 1]

    const inLength = distance(prev, curr)
    const outLength = distance(curr, next)
    const r = Math.min(radius, inLength / 2, outLength / 2)

    if (r < 0.5) {
      d += ` L ${curr.x} ${curr.y}`
      continue
    }

    const entry = lerp(curr, prev, r / inLength)
    const exit = lerp(curr, next, r / outLength)

    d += ` L ${round(entry.x)} ${round(entry.y)}`
    d += ` Q ${round(curr.x)} ${round(curr.y)} ${round(exit.x)} ${round(exit.y)}`
  }

  const last = points[points.length - 1]
  d += ` L ${last.x} ${last.y}`
  return d
}

function distance(a: Point, b: Point): number {
  return Math.hypot(b.x - a.x, b.y - a.y)
}

function lerp(from: Point, to: Point, t: number): Point {
  return { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t }
}

function round(n: number): number {
  return Math.round(n * 100) / 100
}

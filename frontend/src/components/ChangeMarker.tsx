import type { ReactNode } from 'react'
import { PencilLine, Plus, RefreshCw } from 'lucide-react'
import styles from './ChangeMarker.module.css'
import { Badge } from './Badge'
import { Tooltip } from './Tooltip'
import { cx } from '@/lib/cx'
import type { ChangeType } from '@/types/project'

/**
 * The single source of truth for how each AI change type is named and drawn.
 *
 * The spec requires change types to be distinguishable without relying on
 * colour, so every type carries three independent signals: a hue, a glyph, and
 * a Russian label. Anything rendering a change reads from this table.
 */
export const CHANGE_META: Record<
  ChangeType,
  { label: string; description: string; icon: ReactNode; iconSmall: ReactNode }
> = {
  direct: {
    label: 'Изменено',
    description: 'Изменено по вашей команде',
    icon: <PencilLine size={11} />,
    iconSmall: <PencilLine size={9} />,
  },
  created: {
    label: 'Новая',
    description: 'Задача создана AI',
    icon: <Plus size={11} />,
    iconSmall: <Plus size={9} />,
  },
  derived: {
    label: 'Пересчитано',
    description: 'Даты пересчитаны автоматически',
    icon: <RefreshCw size={10} />,
    iconSmall: <RefreshCw size={9} />,
  },
}

/** Compact square glyph for the dense Gantt table marker column. */
export function ChangeMarker({ type }: { type: ChangeType }) {
  const meta = CHANGE_META[type]
  return (
    <Tooltip content={`${meta.label} · ${meta.description}`}>
      <span className={cx(styles.marker, styles[type])} aria-label={meta.label}>
        {meta.iconSmall}
      </span>
    </Tooltip>
  )
}

/** Labelled badge for places with room for words. */
export function ChangeBadge({ type }: { type: ChangeType }) {
  const meta = CHANGE_META[type]
  return (
    <Badge tone={type} icon={meta.icon}>
      {meta.label}
    </Badge>
  )
}

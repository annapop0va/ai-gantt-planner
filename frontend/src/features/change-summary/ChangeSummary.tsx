import { useState } from 'react'
import { CalendarClock } from 'lucide-react'
import styles from './ChangeSummary.module.css'
import { ChangeMarker } from '@/components'
import {
  formatDayMonthLong,
  pluralReceived,
  pluralSubsequent,
  pluralTasks,
  pluralWorkdays,
} from '@/lib/date'
import type { ChangeSet } from '@/types/project'

export interface ChangeSummaryProps {
  changeSet: ChangeSet
  /** Opens the task detail modal for the given id. */
  onSelectTask?: (taskId: string) => void
}

/**
 * The "what just happened" panel shown after a successful AI change (product-spec
 * §16, §18). Three sections — modified / created / recalculated — plus a release
 * impact block that is deliberately the loudest element here, since a slipped
 * release date is the number a PM cares about most.
 */
export function ChangeSummary({ changeSet, onSelectTask }: ChangeSummaryProps) {
  const [derivedExpanded, setDerivedExpanded] = useState(false)
  const { modified, created, derived, release } = changeSet

  return (
    <div className={styles.summary}>
      {release ? (
        <div className={styles.release}>
          <span className={styles.releaseGlyph} aria-hidden>
            <CalendarClock size={15} />
          </span>
          <div className={styles.releaseText}>
            <span className={styles.releaseLabel}>Дата релиза</span>
            <span className={styles.releaseDates}>
              <span className={styles.releaseBefore}>{formatDayMonthLong(release.beforeDate)}</span>
              <span className={styles.releaseAfter}>→ {formatDayMonthLong(release.afterDate)}</span>
              <span className={styles.releaseDelta}>
                +{release.workdayShift} {pluralWorkdays(release.workdayShift)}
              </span>
            </span>
          </div>
        </div>
      ) : null}

      {modified.length > 0 ? (
        <section className={styles.section}>
          <header className={styles.sectionHeader}>
            <ChangeMarker type="direct" />
            <span className={styles.sectionTitle}>Изменено · {modified.length}</span>
          </header>
          <div className={styles.rows}>
            {modified.map((change) => (
              <button
                key={change.taskId}
                type="button"
                className={styles.row}
                onClick={() => onSelectTask?.(change.taskId)}
              >
                <div className={styles.rowName}>{change.name}</div>
                <div className={styles.deltaList}>
                  {change.deltas.map((delta) => (
                    <div key={delta.label} className={styles.deltaRow}>
                      <span className={styles.deltaLabel}>{delta.label}:</span>
                      <span className={styles.deltaBefore}>{delta.before}</span>
                      <span>→</span>
                      <span className={styles.deltaAfter}>{delta.after}</span>
                    </div>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {created.length > 0 ? (
        <section className={styles.section}>
          <header className={styles.sectionHeader}>
            <ChangeMarker type="created" />
            <span className={styles.sectionTitle}>Добавлено · {created.length}</span>
          </header>
          <div className={styles.rows}>
            {created.map((task) => (
              <button
                key={task.taskId}
                type="button"
                className={styles.row}
                onClick={() => onSelectTask?.(task.taskId)}
              >
                <div className={styles.rowName}>{task.name}</div>
                <div className={styles.createdMeta}>
                  {task.assignee ?? 'Не назначен'} · {task.durationWorkdays} дн. ·{' '}
                  {task.plannedEffortHours} ч
                </div>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {derived.length > 0 ? (
        <section className={styles.section}>
          <header className={styles.sectionHeader}>
            <ChangeMarker type="derived" />
            <span className={styles.sectionTitle}>Пересчитано</span>
          </header>
          <p className={styles.derivedSummary}>
            {derived.length} {pluralSubsequent(derived.length)} {pluralTasks(derived.length)}{' '}
            {pluralReceived(derived.length)} новые даты.{' '}
            <button
              type="button"
              className={styles.derivedToggle}
              onClick={() => setDerivedExpanded((v) => !v)}
            >
              {derivedExpanded ? 'Скрыть список' : 'Показать список'}
            </button>
          </p>
          {derivedExpanded ? (
            <div className={styles.rows}>
              {derived.map((task) => (
                <button
                  key={task.taskId}
                  type="button"
                  className={styles.row}
                  onClick={() => onSelectTask?.(task.taskId)}
                >
                  <div className={styles.derivedRow}>
                    <span className={styles.derivedName}>{task.name}</span>
                    <span className={styles.derivedShift}>
                      +{task.workdayShift} {pluralWorkdays(task.workdayShift)}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}

import { useMemo, useState } from 'react'
import { GitPullRequestArrow, Plus } from 'lucide-react'
import styles from './GanttView.module.css'
import { buildGanttModel, changeCounts } from './ganttModel'
import type { GanttLink, GanttRow } from './ganttModel'
import {
  arrowHeadPath,
  barLeft,
  barWidth,
  dependencyPoints,
  rowTop,
  roundedPath,
} from './ganttGeometry'
import type { GanttMetrics } from './ganttGeometry'
import { ChangeMarker } from '@/components/ChangeMarker'
import { Tooltip } from '@/components/Tooltip'
import { cx } from '@/lib/cx'
import { formatDurationFull, formatDurationShort, formatRange } from '@/lib/date'
import type { ChangeSet, Project } from '@/types/project'

export interface GanttViewProps {
  project: Project
  changeSet: ChangeSet | null
  selectedTaskId: string | null
  onSelectTask: (taskId: string) => void
}

const METRICS: GanttMetrics = { dayWidth: 22, rowHeight: 32, barHeight: 16 }

export function GanttView({ project, changeSet, selectedTaskId, onSelectTask }: GanttViewProps) {
  const [hoveredTaskId, setHoveredTaskId] = useState<string | null>(null)
  const [highlightsVisible, setHighlightsVisible] = useState(true)

  const model = useMemo(() => buildGanttModel(project, changeSet), [project, changeSet])
  const counts = useMemo(() => changeCounts(changeSet), [changeSet])
  const hasLinkChanges = (changeSet?.links.length ?? 0) > 0

  const timelineWidth = model.columnCount * METRICS.dayWidth
  const timelineHeight = model.rows.length * METRICS.rowHeight

  const activeTaskId = selectedTaskId ?? hoveredTaskId

  return (
    <section className={styles.gantt} aria-label="Диаграмма Ганта">
      {changeSet ? (
        <div className={styles.legend}>
          <span className={styles.legendTitle}>Изменения AI</span>
          {counts.direct > 0 ? (
            <span className={styles.legendItem}>
              <span className={cx(styles.legendSwatch, styles.swatchDirect)} />
              Изменено <span className={styles.legendCount}>{counts.direct}</span>
            </span>
          ) : null}
          {counts.created > 0 ? (
            <span className={styles.legendItem}>
              <span className={cx(styles.legendSwatch, styles.swatchCreated)} />
              Новая <span className={styles.legendCount}>{counts.created}</span>
            </span>
          ) : null}
          {counts.derived > 0 ? (
            <span className={styles.legendItem}>
              <span className={cx(styles.legendSwatch, styles.swatchDerived)} />
              Пересчитано <span className={styles.legendCount}>{counts.derived}</span>
            </span>
          ) : null}
          {hasLinkChanges ? (
            <span className={styles.legendItem}>
              <GitPullRequestArrow size={12} aria-hidden />
              Связи изменены
            </span>
          ) : null}
          <span className={styles.legendSpacer} />
          <button
            type="button"
            className={styles.legendReset}
            onClick={() => setHighlightsVisible((v) => !v)}
          >
            {highlightsVisible ? 'Скрыть выделение' : 'Показать выделение'}
          </button>
        </div>
      ) : null}

      <div className={styles.scroller}>
        <div className={styles.canvas}>
          <div className={styles.headerRow}>
            <div className={styles.tableCol}>
              <div className={styles.tableHead}>
                <span className={styles.headCell} aria-hidden />
                <span className={styles.headCell}>Задача</span>
                <span className={styles.headCell}>Исполнитель</span>
                <span className={cx(styles.headCell, styles.headRight)}>Длительность</span>
              </div>
            </div>
            <div className={styles.timelineCol} style={{ width: timelineWidth }}>
              <div className={styles.timelineHead}>
                <div className={styles.monthRow}>
                  {model.months.map((month) => (
                    <div
                      key={month.key}
                      className={styles.month}
                      style={{ width: month.span * METRICS.dayWidth }}
                    >
                      {month.label}
                    </div>
                  ))}
                </div>
                <div className={styles.dayRow}>
                  {model.days.map((day) => (
                    <div
                      key={day.iso}
                      className={cx(styles.day, day.isWeekStart && styles.weekStart)}
                    >
                      <span className={styles.dayNumber}>{day.dayOfMonth}</span>
                      <span className={styles.dayName}>{day.weekday}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className={styles.bodyRow}>
            <div className={styles.tableCol}>
              <div className={styles.tableBody}>
                {model.rows.map((row) => (
                  <TableRow
                    key={row.task.id}
                    row={row}
                    selected={row.task.id === selectedTaskId}
                    hovered={row.task.id === hoveredTaskId}
                    highlightsVisible={highlightsVisible}
                    onSelect={onSelectTask}
                    onHover={setHoveredTaskId}
                  />
                ))}
              </div>
            </div>

            <div className={styles.timelineCol} style={{ width: timelineWidth }}>
              <div
                className={styles.timelineBody}
                style={{ height: timelineHeight, width: timelineWidth }}
              >
                {model.rows.map((row) => (
                  <div
                    key={row.task.id}
                    className={cx(
                      styles.timelineRow,
                      row.task.id === hoveredTaskId && styles.timelineRowHovered,
                      row.task.id === selectedTaskId && styles.timelineRowSelected,
                    )}
                    style={{ top: rowTop(row.rowIndex, METRICS) }}
                  />
                ))}

                <svg
                  className={styles.links}
                  width={timelineWidth}
                  height={timelineHeight}
                  aria-hidden
                >
                  {model.links.map((link) => (
                    <LinkPath key={link.id} link={link} model={model} activeTaskId={activeTaskId} />
                  ))}
                </svg>

                {model.rows.map((row) =>
                  row.ghost && highlightsVisible ? (
                    <div
                      key={`ghost-${row.task.id}`}
                      className={styles.ghost}
                      style={{
                        left: barLeft(row.ghost.startIndex, METRICS),
                        width: barWidth(row.ghost.span, METRICS),
                        top: rowTop(row.rowIndex, METRICS) + (METRICS.rowHeight - METRICS.barHeight) / 2,
                      }}
                    />
                  ) : null,
                )}

                {model.rows.map((row) => (
                  <Bar
                    key={row.task.id}
                    row={row}
                    selected={row.task.id === selectedTaskId}
                    highlightsVisible={highlightsVisible}
                    onSelect={onSelectTask}
                    onHover={setHoveredTaskId}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* -------------------------------------------------------------------------- */

function TableRow({
  row,
  selected,
  hovered,
  highlightsVisible,
  onSelect,
  onHover,
}: {
  row: GanttRow
  selected: boolean
  hovered: boolean
  highlightsVisible: boolean
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
}) {
  const { task } = row
  const changeType = highlightsVisible ? row.changeType : null

  return (
    <button
      type="button"
      className={cx(styles.tableRow, selected && styles.rowSelected, hovered && styles.rowHovered)}
      onClick={() => onSelect(task.id)}
      onMouseEnter={() => onHover(task.id)}
      onMouseLeave={() => onHover(null)}
    >
      <span className={styles.marker}>{changeType ? <ChangeMarker type={changeType} /> : null}</span>
      <span className={styles.taskName}>{task.name}</span>
      <span className={cx(styles.assignee, !task.assignee && styles.assigneeEmpty)}>
        {task.assignee ?? 'Не назначен'}
      </span>
      <span className={styles.duration}>
        {formatDurationShort(task.duration_workdays)}
        <span className={styles.durationHours}>· {task.planned_effort_hours} ч</span>
      </span>
    </button>
  )
}

function Bar({
  row,
  selected,
  highlightsVisible,
  onSelect,
  onHover,
}: {
  row: GanttRow
  selected: boolean
  highlightsVisible: boolean
  onSelect: (id: string) => void
  onHover: (id: string | null) => void
}) {
  const { task } = row
  const changeType = highlightsVisible ? row.changeType : null

  const tone =
    changeType === 'direct'
      ? styles.barDirect
      : changeType === 'created'
        ? styles.barCreated
        : changeType === 'derived'
          ? styles.barDerived
          : undefined

  return (
    <Tooltip
      variant="rich"
      content={
        <div>
          <div className={styles.tipTitle}>{task.name}</div>
          <div className={styles.tipGrid}>
            <span className={styles.tipKey}>Исполнитель</span>
            <span className={styles.tipValue}>{task.assignee ?? 'Не назначен'}</span>
            <span className={styles.tipKey}>Даты</span>
            <span className={styles.tipValue}>{formatRange(task.start_date, task.end_date)}</span>
            <span className={styles.tipKey}>Длительность</span>
            <span className={styles.tipValue}>
              {formatDurationFull(task.duration_workdays, task.planned_effort_hours)}
            </span>
          </div>
          {changeType ? (
            <div className={styles.tipBadge}>
              <ChangeMarker type={changeType} />
            </div>
          ) : null}
          <div className={styles.tipHint}>Нажмите, чтобы открыть детали задачи</div>
        </div>
      }
    >
      <div
        role="button"
        tabIndex={0}
        className={cx(styles.bar, tone, selected && styles.barSelected)}
        style={{
          left: barLeft(row.startIndex, METRICS),
          width: barWidth(row.span, METRICS),
          top: rowTop(row.rowIndex, METRICS) + (METRICS.rowHeight - METRICS.barHeight) / 2,
        }}
        onClick={() => onSelect(task.id)}
        onMouseEnter={() => onHover(task.id)}
        onMouseLeave={() => onHover(null)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onSelect(task.id)
          }
        }}
        aria-label={task.name}
      >
        {changeType === 'created' ? (
          <span className={styles.barGlyph}>
            <Plus size={10} />
          </span>
        ) : null}
      </div>
    </Tooltip>
  )
}

function LinkPath({
  link,
  model,
  activeTaskId,
}: {
  link: GanttLink
  model: ReturnType<typeof buildGanttModel>
  activeTaskId: string | null
}) {
  const source = model.rowById.get(link.sourceId)
  const target = model.rowById.get(link.targetId)
  if (!source || !target) return null

  const points = dependencyPoints(source, target, METRICS)
  const path = roundedPath(points)
  const arrow = arrowHeadPath(target, METRICS)
  const active =
    activeTaskId !== null && (link.sourceId === activeTaskId || link.targetId === activeTaskId)

  return (
    <g
      className={cx(
        active && styles.linkActive,
        link.kind === 'added' && styles.linkAdded,
        link.kind === 'removed' && styles.linkRemoved,
      )}
    >
      <path className={styles.linkPath} d={path} />
      {link.kind !== 'removed' ? <path className={styles.linkHead} d={arrow} /> : null}
    </g>
  )
}

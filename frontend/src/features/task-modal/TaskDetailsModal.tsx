import { useMemo } from 'react'
import styles from './TaskDetailsModal.module.css'
import { Badge, ChangeBadge, Modal, TaskChip } from '@/components'
import { formatDurationFull, formatLong } from '@/lib/date'
import type { ChangeSet, Project } from '@/types/project'

export interface TaskDetailsModalProps {
  project: Project
  changeSet: ChangeSet | null
  taskId: string | null
  onClose: () => void
  onNavigate: (taskId: string) => void
}

/**
 * Read-only task detail dialog (product-spec §16). Predecessors/successors are
 * always shown by name — never by UUID — and are clickable so a PM can walk a
 * dependency chain without leaving the dialog.
 */
export function TaskDetailsModal({
  project,
  changeSet,
  taskId,
  onClose,
  onNavigate,
}: TaskDetailsModalProps) {
  const taskById = useMemo(() => new Map(project.tasks.map((t) => [t.id, t])), [project.tasks])
  const task = taskId ? taskById.get(taskId) ?? null : null

  if (!task) return null

  const changeType = changeSet?.byTask[task.id] ?? null

  return (
    <Modal
      open
      onClose={onClose}
      size="md"
      title={task.name}
      subtitle={
        <span className={styles.subtitle}>
          {task.assignee ?? 'Не назначен'}
          <span className={styles.dot}>·</span>
          {formatDurationFull(task.duration_workdays, task.planned_effort_hours)}
        </span>
      }
      headerAside={
        <>
          <Badge tone={task.created_source === 'agent' ? 'accent' : 'neutral'}>
            {task.created_source === 'agent' ? 'Создано AI' : 'Из Excel'}
          </Badge>
          {changeType ? <ChangeBadge type={changeType} /> : null}
        </>
      }
    >
      {task.description ? (
        <p className={styles.description}>{task.description}</p>
      ) : (
        <p className={`${styles.description} ${styles.fieldValueMuted}`}>Описание не заполнено.</p>
      )}

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Сроки и трудоёмкость</div>
        <div className={styles.grid}>
          <Field label="Начало" value={formatLong(task.start_date)} />
          <Field label="Окончание" value={formatLong(task.end_date)} />
          <Field
            label="Длительность"
            value={formatDurationFull(task.duration_workdays, task.planned_effort_hours)}
          />
          <Field
            label="Не ранее"
            value={task.start_not_before ? formatLong(task.start_not_before) : '—'}
            muted={!task.start_not_before}
          />
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Предшественники</div>
        {task.predecessor_ids.length === 0 ? (
          <p className={styles.empty}>Нет предшественников</p>
        ) : (
          <div className={styles.chips}>
            {task.predecessor_ids.map((id) => {
              const related = taskById.get(id)
              if (!related) return null
              return (
                <TaskChip
                  key={id}
                  name={related.name}
                  direction="predecessor"
                  highlight={changeSet?.byTask[id] === 'created'}
                  onClick={() => onNavigate(id)}
                />
              )
            })}
          </div>
        )}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Последующие задачи</div>
        {task.successor_ids.length === 0 ? (
          <p className={styles.empty}>Нет последующих задач</p>
        ) : (
          <div className={styles.chips}>
            {task.successor_ids.map((id) => {
              const related = taskById.get(id)
              if (!related) return null
              return (
                <TaskChip
                  key={id}
                  name={related.name}
                  direction="successor"
                  highlight={changeSet?.byTask[id] === 'created'}
                  onClick={() => onNavigate(id)}
                />
              )
            })}
          </div>
        )}
      </div>
    </Modal>
  )
}

function Field({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <span className={`${styles.fieldValue} ${muted ? styles.fieldValueMuted : ''}`}>{value}</span>
    </div>
  )
}

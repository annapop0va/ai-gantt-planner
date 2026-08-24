import { CalendarClock, ListChecks, Users } from 'lucide-react'
import styles from './ProjectMetricsBar.module.css'
import { ProjectMetric } from '@/components'
import { assigneeCount, releaseDate } from '@/lib/diff'
import { formatDayMonthLong, pluralTasks, pluralWorkdays } from '@/lib/date'
import type { ChangeSet, Project } from '@/types/project'

export interface ProjectMetricsBarProps {
  project: Project
  changeSet: ChangeSet | null
}

/** Compact metrics row above the Gantt (product-spec §16) — task count, team size,
 * and the release date, which gets the loud before/after treatment once an AI
 * change has run. */
export function ProjectMetricsBar({ project, changeSet }: ProjectMetricsBarProps) {
  const release = releaseDate(project)

  return (
    <div className={styles.bar}>
      <ProjectMetric
        icon={<ListChecks size={14} />}
        label="Задачи"
        value={`${project.tasks.length} ${pluralTasks(project.tasks.length)}`}
      />
      <ProjectMetric icon={<Users size={14} />} label="Исполнители" value={`${assigneeCount(project)}`} />
      <ProjectMetric
        icon={<CalendarClock size={14} />}
        label="Релиз"
        value={release ? formatDayMonthLong(release) : '—'}
        previousValue={changeSet?.release ? formatDayMonthLong(changeSet.release.beforeDate) : undefined}
        delta={
          changeSet?.release
            ? `+${changeSet.release.workdayShift} ${pluralWorkdays(changeSet.release.workdayShift)}`
            : undefined
        }
        emphasis={Boolean(changeSet?.release)}
      />
    </div>
  )
}

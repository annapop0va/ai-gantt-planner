import { CheckCircle2, ChartGantt, Download, Loader2, Upload } from 'lucide-react'
import styles from './Header.module.css'
import { PROJECT_DISPLAY_NAME } from './types'
import type { ExportStatus } from './types'
import { Button } from '@/components'
import { formatLong, pluralTasks } from '@/lib/date'
import { cx } from '@/lib/cx'
import type { Project } from '@/types/project'

export interface HeaderProps {
  project: Project
  exportStatus: ExportStatus
  onUploadNew: () => void
  onExport: () => void
}

export function Header({ project, exportStatus, onUploadNew, onExport }: HeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.identity}>
        <span className={styles.glyph} aria-hidden>
          <ChartGantt size={14} />
        </span>
        <div className={styles.text}>
          <span className={styles.name}>{PROJECT_DISPLAY_NAME}</span>
          <span className={styles.supporting}>
            Старт: {formatLong(project.project_start_date)} · {project.tasks.length}{' '}
            {pluralTasks(project.tasks.length)}
          </span>
        </div>
      </div>

      <div className={styles.actions}>
        <Button variant="secondary" iconLeft={<Upload size={14} />} onClick={onUploadNew}>
          Загрузить другой файл
        </Button>
        <Button
          variant="primary"
          className={cx(exportStatus === 'done' && styles.exportDone)}
          iconLeft={
            exportStatus === 'preparing' ? (
              <Loader2 size={14} className={styles.spin} />
            ) : exportStatus === 'done' ? (
              <CheckCircle2 size={14} />
            ) : (
              <Download size={14} />
            )
          }
          disabled={exportStatus === 'preparing'}
          onClick={onExport}
        >
          {exportStatus === 'preparing'
            ? 'Готовим Excel…'
            : exportStatus === 'done'
              ? 'Excel обновлён'
              : 'Экспорт Excel'}
        </Button>
      </div>
    </header>
  )
}

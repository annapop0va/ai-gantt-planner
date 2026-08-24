import styles from './Workspace.module.css'
import { Header } from './Header'
import { ProjectMetricsBar } from './ProjectMetricsBar'
import type { ExportStatus } from './types'
import { GanttView } from '@/features/gantt/GanttView'
import { ChatPanel } from '@/features/chat/ChatPanel'
import type { ChatStatus, ChatTurn } from '@/features/chat/types'
import type { ChangeSet, Project } from '@/types/project'

export interface WorkspaceProps {
  project: Project
  changeSet: ChangeSet | null
  selectedTaskId: string | null
  onSelectTask: (taskId: string) => void
  exportStatus: ExportStatus
  onExport: () => void
  onUploadNew: () => void
  chatTurns: ChatTurn[]
  chatStatus: ChatStatus
  onSendMessage: (text: string) => void
  onRetryLast: () => void
  onShowDependencies: (taskId: string) => void
}

export function Workspace({
  project,
  changeSet,
  selectedTaskId,
  onSelectTask,
  exportStatus,
  onExport,
  onUploadNew,
  chatTurns,
  chatStatus,
  onSendMessage,
  onRetryLast,
  onShowDependencies,
}: WorkspaceProps) {
  return (
    <div className={styles.workspace}>
      <Header project={project} exportStatus={exportStatus} onUploadNew={onUploadNew} onExport={onExport} />
      <div className={styles.body}>
        <div className={styles.ganttColumn}>
          <ProjectMetricsBar project={project} changeSet={changeSet} />
          <GanttView
            project={project}
            changeSet={changeSet}
            selectedTaskId={selectedTaskId}
            onSelectTask={onSelectTask}
          />
        </div>
        <div className={styles.chatColumn}>
          <ChatPanel
            turns={chatTurns}
            status={chatStatus}
            onSend={onSendMessage}
            onRetryLast={onRetryLast}
            onSelectTask={onSelectTask}
            onShowDependencies={onShowDependencies}
          />
        </div>
      </div>
    </div>
  )
}

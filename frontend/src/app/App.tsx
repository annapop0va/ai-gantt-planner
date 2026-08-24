import { useCallback, useEffect, useRef, useState } from 'react'
import styles from './App.module.css'
import { DevStateSwitcher } from './DevStateSwitcher'
import { UploadConfirmDialog } from './UploadConfirmDialog'
import { Workspace } from './Workspace'
import type { DevState, ExportStatus, Screen } from './types'
import { ImportErrorScreen } from '@/features/import/ImportErrorScreen'
import { ImportLoadingScreen } from '@/features/import/ImportLoadingScreen'
import { ImportScreen } from '@/features/import/ImportScreen'
import { looksInvalid } from '@/features/import/scenarios'
import type { ImportIssue } from '@/features/import/scenarios'
import {
  CANONICAL_COMMAND,
  CLARIFICATION_REPLY,
  ERROR_REPLY,
  REJECTED_REPLY,
  SUCCESS_REPLY,
  classifyMessage,
} from '@/features/chat/scenarios'
import type { ChatStatus, ChatTurn } from '@/features/chat/types'
import { TaskDetailsModal } from '@/features/task-modal/TaskDetailsModal'
import type { SelectedFile } from '@/components'
import { ApiError, triggerBlobDownload } from '@/api/client'
import { sendChatMessage } from '@/api/chat'
import { exportProject, getProject, importProject } from '@/api/projects'
import { adaptServerChangeSummary } from './serverChangeSummaryAdapter'
import { computeChangeSet } from '@/lib/diff'
import { projectAfter, projectBefore } from '@/fixtures'
import type { ChangeSet, Project } from '@/types/project'

/** The one real transformation the mock/demo prototype knows — computed once from the fixtures. */
const CANONICAL_CHANGE_SET = computeChangeSet(projectBefore, projectAfter)

/** QA-тестирование карточки пациента — stable across both fixture revisions. */
const QA_TASK_ID = '07e60bee-303e-5d00-bd18-544a4edfac90'
/** Frontend-разработка карточки пациента — the clearest "direct" change for the demo. */
const FRONTEND_TASK_ID = '08f53915-9995-5086-a67f-3882d6d2e4d8'

const AI_THINK_MS = 1400
const DEFAULT_START_DATE = '2026-09-07'
const PROJECT_ID_STORAGE_KEY = 'planpilot.project_id'
const CHAT_DISABLED_REPLY = 'AI-редактирование будет подключено на следующем этапе.'
const EXPORT_FAILED_REPLY = 'Не удалось подготовить Excel-файл. Сервис недоступен.'
const RESTORE_FAILED_MESSAGE =
  'Проект хранился только в памяти сервера и исчез после его перезапуска (или сервер сейчас недоступен). Загрузите файл ещё раз.'

function uid(): string {
  return crypto.randomUUID()
}

/**
 * `handleImportDone` only awaits this promise once the loading-screen animation
 * finishes (~1.9s later per the existing visual, product-spec's "no fake
 * percentage" requirement). A fetch can reject well before that — attach a
 * silent `.catch` immediately so the browser never reports it as an unhandled
 * rejection; the real error is still observed later via `await`.
 */
function trackPending(kind: PendingRequest['kind'], promise: Promise<Project>): PendingRequest {
  promise.catch(() => {})
  return { kind, promise }
}

interface PendingRequest {
  kind: 'import' | 'restore'
  promise: Promise<Project>
}

interface ImportErrorState {
  message?: string
  issues?: ImportIssue[]
  retryable: boolean
}

function toImportIssues(details: unknown[]): ImportIssue[] {
  return details.map((raw) => {
    const detail = (raw ?? {}) as Record<string, unknown>
    return {
      row: typeof detail.row === 'number' ? detail.row : null,
      field: typeof detail.field === 'string' ? detail.field : null,
      message: typeof detail.message === 'string' ? detail.message : 'Ошибка импорта.',
    }
  })
}

export function App() {
  const [screen, setScreen] = useState<Screen>('import')
  const [pendingFile, setPendingFile] = useState<SelectedFile | null>(null)
  const [pendingStartDate, setPendingStartDate] = useState(DEFAULT_START_DATE)
  const [importErrorState, setImportErrorState] = useState<ImportErrorState | null>(null)
  const pendingRequestRef = useRef<PendingRequest | null>(null)

  /** 'mock' drives the fixture-based demo (DevStateSwitcher, canned chat). 'server'
   * means a real backend project is loaded — chat and export switch to real calls. */
  const [dataSource, setDataSource] = useState<'mock' | 'server'>('mock')
  const [serverProject, setServerProject] = useState<Project | null>(null)
  const [projectId, setProjectId] = useState<string | null>(null)
  /** The Gantt highlight/legend for server mode — set from the same adapter
   * output used for the chat's ChangeSummary bubble, so both stay in sync.
   * Persists until the next successful AI command, per spec. */
  const [serverChangeSet, setServerChangeSet] = useState<ChangeSet | null>(null)

  const [projectVersion, setProjectVersion] = useState<'before' | 'after'>('before')
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [uploadConfirmOpen, setUploadConfirmOpen] = useState(false)
  const [exportStatus, setExportStatus] = useState<ExportStatus>('idle')

  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([])
  const [chatStatus, setChatStatus] = useState<ChatStatus>('idle')
  const lastUserMessageRef = useRef<string | null>(null)
  const lastFailedActionRef = useRef<'chat' | 'export'>('chat')

  const project = dataSource === 'server' && serverProject ? serverProject : projectVersion === 'after' ? projectAfter : projectBefore
  const changeSet = dataSource === 'server' ? serverChangeSet : projectVersion === 'after' ? CANONICAL_CHANGE_SET : null

  // Restore a server-mode project after a page reload — the project itself lives
  // only in the backend's in-memory store, so only the id is kept client-side.
  useEffect(() => {
    const savedId = sessionStorage.getItem(PROJECT_ID_STORAGE_KEY)
    if (!savedId) return
    setScreen('importLoading')
    pendingRequestRef.current = trackPending('restore', getProject(savedId))
  }, [])

  const resetToImport = useCallback(() => {
    sessionStorage.removeItem(PROJECT_ID_STORAGE_KEY)
    setScreen('import')
    setPendingFile(null)
    setImportErrorState(null)
    setDataSource('mock')
    setServerProject(null)
    setServerChangeSet(null)
    setProjectId(null)
    setProjectVersion('before')
    setChatTurns([])
    setChatStatus('idle')
    setSelectedTaskId(null)
    setUploadConfirmOpen(false)
    setExportStatus('idle')
  }, [])

  /* --- import ------------------------------------------------------------ */

  const handleBuildPlan = useCallback((file: SelectedFile, startDate: string) => {
    setPendingFile(file)
    setPendingStartDate(startDate)
    setScreen('importLoading')
    pendingRequestRef.current = file.raw
      ? trackPending('import', importProject(file.raw, startDate).then((r) => r.project))
      : null
  }, [])

  const handleImportDone = useCallback(async () => {
    const pending = pendingRequestRef.current
    pendingRequestRef.current = null

    if (pending) {
      try {
        const loadedProject = await pending.promise
        sessionStorage.setItem(PROJECT_ID_STORAGE_KEY, loadedProject.id)
        setDataSource('server')
        setServerProject(loadedProject)
        setServerChangeSet(null)
        setProjectId(loadedProject.id)
        setImportErrorState(null)
        setChatTurns([])
        setChatStatus('idle')
        setSelectedTaskId(null)
        setExportStatus('idle')
        setScreen('workspace')
      } catch (err) {
        if (pending.kind === 'restore') {
          sessionStorage.removeItem(PROJECT_ID_STORAGE_KEY)
          setImportErrorState({ message: RESTORE_FAILED_MESSAGE, issues: [], retryable: false })
        } else {
          const apiError =
            err instanceof ApiError ? err : new ApiError(0, { code: 'UNKNOWN_ERROR', message: 'Не удалось импортировать файл.' })
          setImportErrorState({
            message: apiError.message,
            issues: toImportIssues(apiError.details),
            retryable: true,
          })
        }
        setScreen('importError')
      }
      return
    }

    // Mock path — DevStateSwitcher-fabricated files, no real upload.
    if (pendingFile && looksInvalid(pendingFile.name)) {
      setImportErrorState(null)
      setScreen('importError')
      return
    }
    setDataSource('mock')
    setProjectVersion('before')
    setChatTurns([])
    setChatStatus('idle')
    setSelectedTaskId(null)
    setExportStatus('idle')
    setScreen('workspace')
  }, [pendingFile])

  const handleChooseAnotherFile = useCallback(() => {
    setPendingFile(null)
    setImportErrorState(null)
    setScreen('import')
  }, [])

  const handleRetryImport = useCallback(() => {
    pendingRequestRef.current =
      pendingFile?.raw != null
        ? trackPending('import', importProject(pendingFile.raw, pendingStartDate).then((r) => r.project))
        : null
    setScreen('importLoading')
  }, [pendingFile, pendingStartDate])

  /* --- chat ---------------------------------------------------------------
     Mock mode: only one real transformation exists in the fixtures, so any
     message not deliberately steered toward a failure mode resolves to it —
     see features/chat/scenarios.ts. Server mode: chat is not wired to
     MCP/OpenRouter yet, so it answers with a plain "coming soon" turn. */

  const resolveMockMessage = useCallback((text: string) => {
    const outcome = classifyMessage(text)
    setChatStatus('idle')

    if (outcome === 'success') {
      setProjectVersion('after')
      setChatTurns((turns) => [
        ...turns,
        { id: uid(), role: 'assistant', kind: 'success', text: SUCCESS_REPLY, changeSet: CANONICAL_CHANGE_SET },
      ])
      return
    }
    if (outcome === 'clarification') {
      setChatTurns((turns) => [
        ...turns,
        { id: uid(), role: 'assistant', kind: 'clarification', text: CLARIFICATION_REPLY },
      ])
      return
    }
    if (outcome === 'rejected') {
      setChatTurns((turns) => [
        ...turns,
        { id: uid(), role: 'assistant', kind: 'rejected', text: REJECTED_REPLY, relatedTaskId: QA_TASK_ID },
      ])
      return
    }
    lastFailedActionRef.current = 'chat'
    setChatTurns((turns) => [...turns, { id: uid(), role: 'assistant', kind: 'error', text: ERROR_REPLY }])
  }, [])

  const runMockAiTurn = useCallback(
    (text: string, appendUserTurn: boolean) => {
      if (appendUserTurn) {
        setChatTurns((turns) => [...turns, { id: uid(), role: 'user', text }])
      }
      lastUserMessageRef.current = text
      setChatStatus('processing')
      window.setTimeout(() => resolveMockMessage(text), AI_THINK_MS)
    },
    [resolveMockMessage],
  )

  /** Real POST /chat. Bound to the project state captured at call time (that
   * value is also what `expected_revision` is taken from) — no optimistic
   * mutation happens before the response comes back. */
  const runServerAiTurn = useCallback(
    async (text: string, appendUserTurn: boolean) => {
      if (!serverProject || !projectId) return
      const previousProject = serverProject

      if (appendUserTurn) {
        setChatTurns((turns) => [...turns, { id: uid(), role: 'user', text }])
      }
      lastUserMessageRef.current = text
      lastFailedActionRef.current = 'chat'
      setChatStatus('processing')

      try {
        const result = await sendChatMessage(projectId, text, previousProject.revision)
        setChatStatus('idle')

        if (result.status === 'applied' && result.project) {
          setServerProject(result.project)
          const changeSet = result.change_summary
            ? adaptServerChangeSummary(result.change_summary, previousProject, result.project)
            : null
          // Same object backs both the chat bubble's ChangeSummary and the
          // Gantt highlight/legend — they must never show different diffs.
          setServerChangeSet(changeSet)
          setChatTurns((turns) => [
            ...turns,
            changeSet
              ? { id: uid(), role: 'assistant', kind: 'success', text: result.message, changeSet }
              : { id: uid(), role: 'assistant', kind: 'disabled', text: result.message },
          ])
          return
        }
        if (result.status === 'clarification_required') {
          setChatTurns((turns) => [
            ...turns,
            { id: uid(), role: 'assistant', kind: 'clarification', text: result.message },
          ])
          return
        }
        // rejected — the project is unchanged; the backend does not name a
        // single related task, so "Показать зависимости" stays hidden.
        setChatTurns((turns) => [
          ...turns,
          { id: uid(), role: 'assistant', kind: 'rejected', text: result.message, relatedTaskId: null },
        ])
      } catch (err) {
        setChatStatus('idle')

        if (err instanceof ApiError && err.code === 'AI_NOT_CONFIGURED') {
          setChatTurns((turns) => [
            ...turns,
            { id: uid(), role: 'assistant', kind: 'disabled', text: CHAT_DISABLED_REPLY },
          ])
          return
        }

        if (err instanceof ApiError && err.status === 409) {
          // Someone/something else changed the project while this request was
          // in flight. Refetch so the UI reflects reality, but never resend
          // the user's message automatically.
          try {
            setServerProject(await getProject(projectId))
          } catch {
            // Best effort — worst case the user sees the pre-conflict project
            // until their next successful action refreshes it.
          }
          setChatTurns((turns) => [
            ...turns,
            {
              id: uid(),
              role: 'assistant',
              kind: 'error',
              text: 'План изменился, пока обрабатывался запрос. Мы обновили данные — проверьте план и отправьте запрос ещё раз.',
            },
          ])
          return
        }

        const message = err instanceof ApiError ? `Не удалось обработать запрос: ${err.message}` : ERROR_REPLY
        setChatTurns((turns) => [...turns, { id: uid(), role: 'assistant', kind: 'error', text: message }])
      }
    },
    [serverProject, projectId],
  )

  const handleSendMessage = useCallback(
    (text: string) => {
      if (dataSource === 'server') {
        runServerAiTurn(text, true)
        return
      }
      runMockAiTurn(text, true)
    },
    [dataSource, runMockAiTurn, runServerAiTurn],
  )

  const handleShowDependencies = useCallback((taskId: string) => setSelectedTaskId(taskId), [])

  /* --- export / upload confirmation --------------------------------------- */

  const handleExport = useCallback(() => {
    setExportStatus('preparing')

    if (dataSource === 'server' && projectId) {
      exportProject(projectId)
        .then(({ blob, filename }) => {
          triggerBlobDownload(blob, filename)
          setExportStatus('done')
          window.setTimeout(() => setExportStatus('idle'), 2200)
        })
        .catch((err) => {
          setExportStatus('idle')
          lastFailedActionRef.current = 'export'
          const message = err instanceof ApiError ? err.message : EXPORT_FAILED_REPLY
          setChatTurns((turns) => [...turns, { id: uid(), role: 'assistant', kind: 'error', text: message }])
        })
      return
    }

    window.setTimeout(() => {
      setExportStatus('done')
      window.setTimeout(() => setExportStatus('idle'), 2200)
    }, 900)
  }, [dataSource, projectId])

  const handleRetryLast = useCallback(() => {
    if (lastFailedActionRef.current === 'export') {
      handleExport()
      return
    }
    if (!lastUserMessageRef.current) return
    if (dataSource === 'server') {
      runServerAiTurn(lastUserMessageRef.current, false)
    } else {
      runMockAiTurn(lastUserMessageRef.current, false)
    }
  }, [dataSource, handleExport, runMockAiTurn, runServerAiTurn])

  const handleUploadNewClick = useCallback(() => setUploadConfirmOpen(true), [])

  /* --- dev state switcher -------------------------------------------------- */

  const applyDevState = useCallback(
    (state: DevState) => {
      sessionStorage.removeItem(PROJECT_ID_STORAGE_KEY)
      setDataSource('mock')
      setServerProject(null)
      setServerChangeSet(null)
      setProjectId(null)

      switch (state) {
        case 'import':
          resetToImport()
          return
        case 'importLoading':
          setPendingFile({ name: 'sample_patient_card_project.xlsx', size: 24_576 })
          setImportErrorState(null)
          setScreen('importLoading')
          return
        case 'importError':
          setPendingFile({ name: 'sample_patient_card_project_invalid.xlsx', size: 24_576 })
          setImportErrorState(null)
          setScreen('importError')
          return
        case 'workspaceBeforeAi':
          setProjectVersion('before')
          setChatTurns([])
          setChatStatus('idle')
          setSelectedTaskId(null)
          setUploadConfirmOpen(false)
          setExportStatus('idle')
          setScreen('workspace')
          return
        case 'aiProcessing':
          setProjectVersion('before')
          setChatTurns([])
          setSelectedTaskId(null)
          setUploadConfirmOpen(false)
          setScreen('workspace')
          runMockAiTurn(CANONICAL_COMMAND, true)
          return
        case 'aiSuccess':
          setProjectVersion('after')
          setChatStatus('idle')
          setSelectedTaskId(null)
          setUploadConfirmOpen(false)
          setChatTurns([
            { id: uid(), role: 'user', text: CANONICAL_COMMAND },
            { id: uid(), role: 'assistant', kind: 'success', text: SUCCESS_REPLY, changeSet: CANONICAL_CHANGE_SET },
          ])
          setScreen('workspace')
          return
        case 'clarification':
          setProjectVersion('before')
          setChatStatus('idle')
          setSelectedTaskId(null)
          setUploadConfirmOpen(false)
          setChatTurns([
            { id: uid(), role: 'user', text: 'Перенеси задачу с API на следующую неделю' },
            { id: uid(), role: 'assistant', kind: 'clarification', text: CLARIFICATION_REPLY },
          ])
          setScreen('workspace')
          return
        case 'rejected':
          setProjectVersion('before')
          setChatStatus('idle')
          setSelectedTaskId(null)
          setUploadConfirmOpen(false)
          setChatTurns([
            { id: uid(), role: 'user', text: 'Перенеси QA-тестирование на более раннюю дату' },
            { id: uid(), role: 'assistant', kind: 'rejected', text: REJECTED_REPLY, relatedTaskId: QA_TASK_ID },
          ])
          setScreen('workspace')
          return
        case 'technicalError':
          setProjectVersion('before')
          setChatStatus('idle')
          setSelectedTaskId(null)
          setUploadConfirmOpen(false)
          lastUserMessageRef.current = CANONICAL_COMMAND
          lastFailedActionRef.current = 'chat'
          setChatTurns([
            { id: uid(), role: 'user', text: CANONICAL_COMMAND },
            { id: uid(), role: 'assistant', kind: 'error', text: ERROR_REPLY },
          ])
          setScreen('workspace')
          return
        case 'taskModal':
          setProjectVersion('after')
          setChatStatus('idle')
          setUploadConfirmOpen(false)
          setChatTurns([
            { id: uid(), role: 'user', text: CANONICAL_COMMAND },
            { id: uid(), role: 'assistant', kind: 'success', text: SUCCESS_REPLY, changeSet: CANONICAL_CHANGE_SET },
          ])
          setScreen('workspace')
          setSelectedTaskId(FRONTEND_TASK_ID)
          return
        case 'uploadConfirmation':
          setProjectVersion('after')
          setChatStatus('idle')
          setSelectedTaskId(null)
          setChatTurns([
            { id: uid(), role: 'user', text: CANONICAL_COMMAND },
            { id: uid(), role: 'assistant', kind: 'success', text: SUCCESS_REPLY, changeSet: CANONICAL_CHANGE_SET },
          ])
          setScreen('workspace')
          setUploadConfirmOpen(true)
          return
        case 'exportSuccess':
          setProjectVersion('after')
          setChatStatus('idle')
          setSelectedTaskId(null)
          setUploadConfirmOpen(false)
          setChatTurns([
            { id: uid(), role: 'user', text: CANONICAL_COMMAND },
            { id: uid(), role: 'assistant', kind: 'success', text: SUCCESS_REPLY, changeSet: CANONICAL_CHANGE_SET },
          ])
          setScreen('workspace')
          setExportStatus('done')
          return
      }
    },
    [resetToImport, runMockAiTurn],
  )

  return (
    <div className={styles.root}>
      {screen === 'import' ? <ImportScreen onBuildPlan={handleBuildPlan} /> : null}

      {screen === 'importLoading' ? <ImportLoadingScreen onDone={handleImportDone} /> : null}

      {screen === 'importError' ? (
        <ImportErrorScreen
          fileName={pendingFile?.name ?? 'project.xlsx'}
          onChooseAnother={handleChooseAnotherFile}
          onRetry={handleRetryImport}
          message={importErrorState?.message}
          issues={importErrorState?.issues}
          retryable={importErrorState?.retryable ?? true}
        />
      ) : null}

      {screen === 'workspace' ? (
        <>
          <Workspace
            project={project}
            changeSet={changeSet}
            selectedTaskId={selectedTaskId}
            onSelectTask={setSelectedTaskId}
            exportStatus={exportStatus}
            onExport={handleExport}
            onUploadNew={handleUploadNewClick}
            chatTurns={chatTurns}
            chatStatus={chatStatus}
            onSendMessage={handleSendMessage}
            onRetryLast={handleRetryLast}
            onShowDependencies={handleShowDependencies}
          />

          <TaskDetailsModal
            project={project}
            changeSet={changeSet}
            taskId={selectedTaskId}
            onClose={() => setSelectedTaskId(null)}
            onNavigate={setSelectedTaskId}
          />

          <UploadConfirmDialog
            open={uploadConfirmOpen}
            onCancel={() => setUploadConfirmOpen(false)}
            onExport={() => {
              handleExport()
              setUploadConfirmOpen(false)
            }}
            onUploadNew={() => {
              setUploadConfirmOpen(false)
              resetToImport()
            }}
          />
        </>
      ) : null}

      <DevStateSwitcher onJump={applyDevState} />
    </div>
  )
}

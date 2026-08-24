import { AlertTriangle } from 'lucide-react'
import styles from './ImportErrorScreen.module.css'
import { DEMO_IMPORT_ISSUES } from './scenarios'
import type { ImportIssue } from './scenarios'
import { Button } from '@/components'

export interface ImportErrorScreenProps {
  fileName: string
  /** Omit to hide "Выбрать другой файл" — there is no file yet (e.g. the
   * backend-unavailable cold-start case). */
  onChooseAnother?: () => void
  onRetry: () => void
  /** Overrides the default demo title — used for non-import failures (e.g. "Сервер пока недоступен"). */
  title?: string
  /** Overrides the default demo copy — used for real server-mode failures. */
  message?: string
  /** Overrides the canned demo issues. Pass `[]` to hide the issue list entirely. */
  issues?: ImportIssue[]
  /** Hides the "Попробовать снова" action when retrying cannot help (e.g. a lost session). */
  retryable?: boolean
}

export function ImportErrorScreen({
  fileName,
  onChooseAnother,
  onRetry,
  title = 'Не удалось импортировать план',
  message,
  issues = DEMO_IMPORT_ISSUES,
  retryable = true,
}: ImportErrorScreenProps) {
  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.head}>
          <span className={styles.glyph} aria-hidden>
            <AlertTriangle size={18} />
          </span>
          <div className={styles.headText}>
            <h1 className={styles.title}>{title}</h1>
            <p className={styles.subtitle}>
              {message ?? (
                <>
                  В файле <span className={styles.fileName}>{fileName}</span> найдены ошибки.
                  Исправьте их и загрузите файл снова.
                </>
              )}
            </p>
          </div>
        </div>

        {issues.length > 0 ? (
          <>
            <span className={styles.issueLabel}>Найденные ошибки · {issues.length}</span>
            <div className={styles.issues}>
              {issues.map((issue, index) => (
                <div key={`${issue.row}-${issue.field}-${index}`} className={styles.issue}>
                  <span className={styles.issueRow}>{issue.row != null ? `Стр. ${issue.row}` : 'Файл'}</span>
                  <div className={styles.issueBody}>
                    {issue.field ? <span className={styles.issueField}>{issue.field}</span> : null}
                    <span className={styles.issueMessage}>{issue.message}</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : null}

        <div className={styles.actions}>
          {onChooseAnother ? (
            <Button variant="secondary" size="lg" onClick={onChooseAnother}>
              Выбрать другой файл
            </Button>
          ) : null}
          {retryable ? (
            <Button variant="primary" size="lg" onClick={onRetry}>
              Попробовать снова
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}

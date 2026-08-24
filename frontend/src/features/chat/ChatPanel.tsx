import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Loader2, RotateCcw, Send, Sparkles } from 'lucide-react'
import styles from './ChatPanel.module.css'
import { CANONICAL_COMMAND, EXAMPLE_PROMPTS, SUGGESTED_PROMPTS } from './scenarios'
import type { ChatStatus, ChatTurn } from './types'
import { Alert, Button, IconButton, Textarea } from '@/components'
import { ChangeSummary } from '@/features/change-summary/ChangeSummary'
import { cx } from '@/lib/cx'

export interface ChatPanelProps {
  turns: ChatTurn[]
  status: ChatStatus
  onSend: (text: string) => void
  onRetryLast: () => void
  onSelectTask: (taskId: string) => void
  onShowDependencies: (taskId: string) => void
}

export function ChatPanel({
  turns,
  status,
  onSend,
  onRetryLast,
  onSelectTask,
  onShowDependencies,
}: ChatPanelProps) {
  const [draft, setDraft] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const isEmpty = turns.length === 0
  const isProcessing = status === 'processing'

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  }, [turns.length, status])

  const fillDraft = (text: string) => {
    setDraft(text)
    textareaRef.current?.focus()
  }

  const submit = () => {
    const text = draft.trim()
    if (!text || isProcessing) return
    onSend(text)
    setDraft('')
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <aside className={styles.panel} aria-label="AI-чат">
      <div className={styles.header}>
        <span className={styles.headerGlyph} aria-hidden>
          <Sparkles size={14} />
        </span>
        <div className={styles.headerText}>
          <span className={styles.headerTitle}>AI-помощник</span>
          <span className={styles.headerSupporting}>Управляйте планом обычным языком</span>
        </div>
      </div>

      {isEmpty ? (
        <div className={styles.empty}>
          <div className={styles.emptyIntro}>
            <span className={styles.emptyGlyph} aria-hidden>
              <Sparkles size={18} />
            </span>
            <span className={styles.emptyTitle}>Опишите, что нужно изменить в плане</span>
            <span className={styles.emptySupporting}>
              AI выполнит структурированные операции и пересчитает зависимости
            </span>
          </div>

          <div className={styles.promptGroup}>
            <span className={styles.promptGroupLabel}>Быстрые команды</span>
            <div className={styles.chips}>
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button key={prompt} type="button" className={styles.chip} onClick={() => fillDraft(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.promptGroup}>
            <span className={styles.promptGroupLabel}>Примеры команд</span>
            <div className={styles.exampleList}>
              {EXAMPLE_PROMPTS.map((example) => (
                <button
                  key={example.text}
                  type="button"
                  className={styles.exampleItem}
                  onClick={() => (example.runImmediately ? onSend(example.text) : fillDraft(example.text))}
                >
                  {example.text}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className={styles.thread} ref={threadRef}>
          {turns.map((turn) => (
            <Turn
              key={turn.id}
              turn={turn}
              onSelectTask={onSelectTask}
              onShowDependencies={onShowDependencies}
              onRetry={onRetryLast}
            />
          ))}
          {isProcessing ? (
            <div className={cx(styles.turn, styles.turnAssistant)}>
              <div className={styles.processing}>
                <Loader2 size={14} className={styles.spinner} aria-hidden />
                Анализирую план…
              </div>
            </div>
          ) : null}
        </div>
      )}

      <div className={styles.composer}>
        <div className={styles.demoHelper}>
          <span className={styles.demoHelperLabelRow}>
            <span className={styles.demoTag}>DEMO</span>
            <span className={styles.demoLabel}>{CANONICAL_COMMAND}</span>
          </span>
          <Button size="sm" variant="ghost" fullWidth onClick={() => fillDraft(CANONICAL_COMMAND)}>
            Запустить demo-сценарий
          </Button>
        </div>

        <div className={styles.composerRow}>
          <Textarea
            textareaRef={textareaRef}
            className={styles.textarea}
            placeholder="Напишите, что изменить в плане…"
            rows={1}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isProcessing}
          />
          <IconButton
            label="Отправить"
            icon={<Send size={15} />}
            variant="accent"
            className={styles.sendButton}
            onClick={submit}
            disabled={!draft.trim() || isProcessing}
          />
        </div>
        <span className={styles.composerHint}>Enter — отправить · Shift + Enter — новая строка</span>
      </div>
    </aside>
  )
}

function Turn({
  turn,
  onSelectTask,
  onShowDependencies,
  onRetry,
}: {
  turn: ChatTurn
  onSelectTask: (taskId: string) => void
  onShowDependencies: (taskId: string) => void
  onRetry: () => void
}) {
  if (turn.role === 'user') {
    return (
      <div className={cx(styles.turn, styles.turnUser)}>
        <div className={cx(styles.bubble, styles.bubbleUser)}>{turn.text}</div>
      </div>
    )
  }

  if (turn.kind === 'success') {
    return (
      <div className={cx(styles.turn, styles.turnAssistant)}>
        <div className={cx(styles.bubble, styles.bubbleAssistant)}>{turn.text}</div>
        <div className={styles.assistantCard}>
          <span className={styles.assistantMeta}>Что изменилось</span>
          <ChangeSummary changeSet={turn.changeSet} onSelectTask={onSelectTask} />
        </div>
      </div>
    )
  }

  if (turn.kind === 'clarification' || turn.kind === 'disabled') {
    return (
      <div className={cx(styles.turn, styles.turnAssistant)}>
        <div className={cx(styles.bubble, styles.bubbleAssistant)}>{turn.text}</div>
      </div>
    )
  }

  if (turn.kind === 'rejected') {
    return (
      <div className={cx(styles.turn, styles.turnAssistant)}>
        <Alert
          tone="warning"
          actions={
            turn.relatedTaskId ? (
              <Button size="sm" variant="secondary" onClick={() => onShowDependencies(turn.relatedTaskId!)}>
                Показать зависимости
              </Button>
            ) : undefined
          }
        >
          {turn.text}
        </Alert>
      </div>
    )
  }

  return (
    <div className={cx(styles.turn, styles.turnAssistant)}>
      <Alert
        tone="error"
        actions={
          <Button size="sm" variant="secondary" iconLeft={<RotateCcw size={13} />} onClick={onRetry}>
            Повторить
          </Button>
        }
      >
        {turn.text}
      </Alert>
    </div>
  )
}

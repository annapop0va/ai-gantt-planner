import { useState } from 'react'
import { ChartGantt, Download } from 'lucide-react'
import styles from './ImportScreen.module.css'
import { REQUIRED_COLUMNS } from './scenarios'
import { Alert, Button, DateInput, Dropzone } from '@/components'
import type { SelectedFile } from '@/components'

export interface ImportScreenProps {
  onBuildPlan: (file: SelectedFile, startDate: string) => void
  /** A calm, one-off informational message shown above the card — e.g. after
   * an in-memory server session was lost to a restart. Not an error state. */
  notice?: string | null
}

const DEFAULT_START_DATE = '2026-09-07'

export function ImportScreen({ onBuildPlan, notice }: ImportScreenProps) {
  const [file, setFile] = useState<SelectedFile | null>(null)
  const [startDate, setStartDate] = useState(DEFAULT_START_DATE)

  return (
    <div className={styles.page}>
      <div className={styles.wrap}>
        {notice ? (
          <Alert tone="info" className={styles.notice}>
            {notice}
          </Alert>
        ) : null}

        <div className={styles.wordmark}>
          <span className={styles.wordmarkGlyph} aria-hidden>
            <ChartGantt size={16} />
          </span>
          <span className={styles.wordmarkText}>
            <span className={styles.wordmarkName}>PlanPilot</span>
            <span className={styles.wordmarkDescriptor}>AI project planning</span>
          </span>
        </div>

        <div className={styles.card}>
          <div className={styles.heading}>
            <h1 className={styles.title}>Загрузите проектный план</h1>
            <p className={styles.subtitle}>
              Постройте диаграмму Гантта и редактируйте план обычным языком
            </p>
          </div>

          <div className={styles.section}>
            <Dropzone file={file} onSelect={setFile} onClear={() => setFile(null)} />

            <div className={styles.sampleRow}>
              <a className={styles.sampleLink} href="/sample_patient_card_project.xlsx" download>
                <Download size={13} aria-hidden />
                Скачать пример Excel
              </a>
            </div>
          </div>

          <div className={styles.section}>
            <DateInput
              label="Дата начала проекта"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </div>

          <div className={styles.section}>
            <div className={styles.columns}>
              <span className={styles.columnsLabel}>Обязательные колонки</span>
              <div className={styles.columnList}>
                {REQUIRED_COLUMNS.map((column) => (
                  <span key={column.name} className={styles.columnItem}>
                    <span className={styles.columnName}>{column.name}</span>
                    <span className={styles.columnHint}>· {column.hint}</span>
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className={styles.cta}>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              disabled={!file}
              onClick={() => file && onBuildPlan(file, startDate)}
            >
              Построить план
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

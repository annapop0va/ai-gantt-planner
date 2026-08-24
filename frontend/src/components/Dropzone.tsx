import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { FileSpreadsheet, Upload, X } from 'lucide-react'
import styles from './Dropzone.module.css'
import { IconButton } from './IconButton'
import { cx } from '@/lib/cx'

export interface SelectedFile {
  name: string
  /** Bytes. Rendered as MB. */
  size: number
  /**
   * The underlying browser File, when one exists — absent for the mock/dev
   * states that fabricate a `SelectedFile` without a real pick. Its presence
   * is what tells the app this is a real import (see app/api).
   */
  raw?: File
}

export interface DropzoneProps {
  file: SelectedFile | null
  onSelect: (file: SelectedFile) => void
  onClear: () => void
  title?: string
  supporting?: string
  accept?: string
}

export function Dropzone({
  file,
  onSelect,
  onClear,
  title = 'Перетащите Excel сюда или выберите файл',
  supporting = '.xlsx · до 5 MB · до 500 задач',
  accept = '.xlsx',
}: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  if (file) {
    return (
      <div className={styles.selected}>
        <span className={styles.fileGlyph}>
          <FileSpreadsheet size={16} aria-hidden />
        </span>
        <span className={styles.fileMeta}>
          <span className={styles.fileName}>{file.name}</span>
          <span className={styles.fileSize}>{formatSize(file.size)} · Excel</span>
        </span>
        <IconButton label="Убрать файл" icon={<X size={14} />} onClick={onClear} />
      </div>
    )
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) onSelect({ name: dropped.name, size: dropped.size, raw: dropped })
  }

  return (
    <div
      role="button"
      tabIndex={0}
      className={cx(styles.dropzone, dragging && styles.active)}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          inputRef.current?.click()
        }
      }}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <span className={styles.glyph}>
        <Upload size={16} aria-hidden />
      </span>
      <span className={styles.title}>
        Перетащите Excel сюда или{' '}
        <span className={styles.titleAccent}>выберите файл</span>
        <span className="srOnly">{title}</span>
      </span>
      <span className={styles.supporting}>{supporting}</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className={styles.input}
        tabIndex={-1}
        onChange={(event) => {
          const picked = event.target.files?.[0]
          if (picked) onSelect({ name: picked.name, size: picked.size, raw: picked })
          event.target.value = ''
        }}
      />
    </div>
  )
}

function formatSize(bytes: number): string {
  if (bytes <= 0) return '—'
  const kb = bytes / 1024
  if (kb < 1000) return `${Math.max(1, Math.round(kb))} KB`
  return `${(kb / 1024).toFixed(1).replace('.', ',')} MB`
}

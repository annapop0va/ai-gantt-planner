import styles from './UploadConfirmDialog.module.css'
import { Button, Modal } from '@/components'

export interface UploadConfirmDialogProps {
  open: boolean
  onCancel: () => void
  onExport: () => void
  onUploadNew: () => void
}

export function UploadConfirmDialog({ open, onCancel, onExport, onUploadNew }: UploadConfirmDialogProps) {
  if (!open) return null

  return (
    <Modal
      open={open}
      onClose={onCancel}
      size="sm"
      title="Загрузить новый проект?"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            Отмена
          </Button>
          <Button variant="secondary" onClick={onExport}>
            Экспортировать
          </Button>
          <Button variant="primary" onClick={onUploadNew}>
            Загрузить новый
          </Button>
        </>
      }
    >
      <p className={styles.text}>
        Текущий план хранится только в этой сессии. Перед загрузкой нового файла рекомендуется
        экспортировать изменения.
      </p>
    </Modal>
  )
}

/**
 * Thin fetch wrapper — deliberately not Axios/TanStack Query. The app makes
 * three request shapes total (import, get, export); a request library buys
 * nothing here that `fetch` doesn't already give us.
 */

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export interface ApiErrorPayload {
  code: string
  message: string
  details?: unknown[]
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown[]

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code
    this.details = payload.details ?? []
  }
}

async function readErrorPayload(response: Response): Promise<ApiErrorPayload> {
  try {
    return (await response.json()) as ApiErrorPayload
  } catch {
    return { code: 'UNKNOWN_ERROR', message: `Сервер вернул ошибку ${response.status}.` }
  }
}

async function doFetch(path: string, init?: RequestInit): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new ApiError(0, { code: 'NETWORK_ERROR', message: 'Не удалось связаться с сервером.' })
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorPayload(response))
  }
  return response
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await doFetch(path, init)
  return response.json() as Promise<T>
}

export interface DownloadedFile {
  blob: Blob
  filename: string | null
}

export async function apiRequestBlob(path: string, init?: RequestInit): Promise<DownloadedFile> {
  const response = await doFetch(path, init)
  const filename = parseFilenameFromDisposition(response.headers.get('content-disposition'))
  const blob = await response.blob()
  return { blob, filename }
}

function parseFilenameFromDisposition(disposition: string | null): string | null {
  if (!disposition) return null
  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  if (utf8Match) return decodeURIComponent(utf8Match[1])
  const plainMatch = /filename="?([^";]+)"?/i.exec(disposition)
  return plainMatch ? plainMatch[1] : null
}

/** Saves a Blob the browser fetched — never a real filesystem write, just the standard download-link trick. */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

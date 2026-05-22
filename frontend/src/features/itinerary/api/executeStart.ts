import type { ExecuteRequest, ExecutionStartResponse } from '../model/types'
import { buildApiUrl } from '../../../shared/lib/url'

export async function executeStart(payload: ExecuteRequest): Promise<ExecutionStartResponse> {
  const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
  const url = buildApiUrl('/execute/start', base)

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `HTTP ${res.status}`)
  }

  return (await res.json()) as ExecutionStartResponse
}

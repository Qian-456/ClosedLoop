import type { InvokeResponse } from '../model/types'
import { buildApiUrl } from '../../../shared/lib/url'

export async function invoke(userInput: string): Promise<InvokeResponse> {
  const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
  const url = buildApiUrl('/invoke', base)

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user_input: userInput }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `HTTP ${res.status}`)
  }

  return (await res.json()) as InvokeResponse
}

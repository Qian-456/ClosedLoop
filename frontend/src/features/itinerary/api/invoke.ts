import type { InvokeResponse } from '../model/types'
import { buildApiUrl } from '../../../shared/lib/url'

export async function invoke(userInput: string, threadId: string): Promise<InvokeResponse> {
  const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
  const url = buildApiUrl('/invoke', base)
  
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user_input: userInput, thread_id: threadId }),
  })

  if (!response.ok) {
    throw new Error('Failed to invoke graph')
  }

  return response.json()
}

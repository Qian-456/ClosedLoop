import type { InvokeResponse, InvokeStreamEvent } from '../model/types'
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

type InvokeStreamOptions = {
  onEvent: (event: InvokeStreamEvent) => void
}

function parseSseBlock(block: string): InvokeStreamEvent | null {
  let eventName = ''
  let dataText = ''

  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim()
      continue
    }

    if (line.startsWith('data:')) {
      dataText += line.slice('data:'.length).trim()
    }
  }

  if (!eventName || !dataText) {
    return null
  }

  const data = JSON.parse(dataText) as InvokeStreamEvent['data']
  if (
    eventName === 'message' ||
    eventName === 'bubble' ||
    eventName === 'result' ||
    eventName === 'done' ||
    eventName === 'error'
  ) {
    return {
      event: eventName,
      data,
    } as InvokeStreamEvent
  }

  return null
}

export async function invokeStream(
  userInput: string,
  threadId: string,
  options: InvokeStreamOptions,
): Promise<void> {
  const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
  const url = buildApiUrl('/invoke/stream', base)

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ user_input: userInput, thread_id: threadId }),
  })

  if (!response.ok) {
    throw new Error('Failed to invoke graph stream')
  }

  if (!response.body) {
    throw new Error('响应不包含可读取的流')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''

    for (const block of blocks) {
      const event = parseSseBlock(block.trim())
      if (!event) {
        continue
      }

      options.onEvent(event)
      if (event.event === 'error') {
        throw new Error(event.data.message)
      }
    }
  }

  const tailEvent = parseSseBlock(buffer.trim())
  if (tailEvent) {
    options.onEvent(tailEvent)
    if (tailEvent.event === 'error') {
      throw new Error(tailEvent.data.message)
    }
  }
}

export async function invokeStreamResume(
  threadId: string,
  resume: Record<string, unknown>,
  options: InvokeStreamOptions,
): Promise<void> {
  const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
  const url = buildApiUrl('/invoke/stream', base)

  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), 5000)

  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId, resume }),
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('请求超时，可重试')
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }

  if (!response.ok) {
    throw new Error('Failed to invoke graph stream resume')
  }

  if (!response.body) {
    throw new Error('响应不包含可读取的流')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''

    for (const block of blocks) {
      const event = parseSseBlock(block.trim())
      if (!event) {
        continue
      }

      options.onEvent(event)
      if (event.event === 'error') {
        throw new Error(event.data.message)
      }
    }
  }

  const tailEvent = parseSseBlock(buffer.trim())
  if (tailEvent) {
    options.onEvent(tailEvent)
    if (tailEvent.event === 'error') {
      throw new Error(tailEvent.data.message)
    }
  }
}

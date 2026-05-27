import { afterEach, describe, expect, it, vi } from 'vitest'

import { invokeStream } from '../invoke'
import type { InvokeStreamEvent } from '../../model/types'

function expectStatefulEvent(event: InvokeStreamEvent): Extract<InvokeStreamEvent, { event: 'state' | 'done' }> {
  if (event.event === 'error') {
    throw new Error('unexpected error event')
  }
  return event
}

function createSseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })

  return new Response(stream, {
    status: 200,
    headers: {
      'content-type': 'text/event-stream',
    },
  })
}

describe('invokeStream', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('按顺序解析跨 chunk 的 state 与 done 事件', async () => {
    const events: InvokeStreamEvent[] = []

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        createSseResponse([
          'event: state\n',
          'data: {"state":{"messages":[{"type":"human","content":"你好"}]}}\n\n',
          'event: state\n' +
            'data: {"state":{"messages":[{"type":"human","content":"你好"},{"type":"ai","content":"正在规划"}]}}\n\n',
          'event: done\n',
          'data: {"state":{"messages":[{"type":"human","content":"你好"},{"type":"ai","content":"最终结果"}]}}\n\n',
        ]),
      ),
    )

    await invokeStream('你好', 'thread_001', {
      onEvent(event) {
        events.push(event)
      },
    })

    expect(events).toHaveLength(3)
    expect(events[0].event).toBe('state')
    expect(events[1].event).toBe('state')
    expect(events[2].event).toBe('done')
    expect(expectStatefulEvent(events[1]).data.state.messages?.[1].content).toBe('正在规划')
    expect(expectStatefulEvent(events[2]).data.state.messages?.[1].content).toBe('最终结果')
  })

  it('遇到 error 事件时抛出服务端错误', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        createSseResponse([
          'event: error\n',
          'data: {"message":"stream failed"}\n\n',
        ]),
      ),
    )

    await expect(
      invokeStream('你好', 'thread_002', {
        onEvent() {},
      }),
    ).rejects.toThrow('stream failed')
  })
})

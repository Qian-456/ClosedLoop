import { afterEach, describe, expect, it, vi } from 'vitest'

import { invokeStream } from '../invoke'
import type { InvokeStreamEvent } from '../../model/types'

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

  it('按顺序解析跨 chunk 的 message、bubble、result 与 done 事件', async () => {
    const events: InvokeStreamEvent[] = []

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        createSseResponse([
          'event: bubble\n',
          'data: {"phase":"bootstrap","text":"正在理解你的需求","entries":[{"kind":"step","title":"进入流程","summary":"正在理解你的需求"}],"status":"running"}\n\n',
          'event: message\n' +
            'data: {"text":"我先帮你拆解需求"}\n\n',
          'event: bubble\n' +
            'data: {"phase":"plan_trip","step":"plan_trip","node":"plan_trip","text":"正在规划方案","entries":[{"kind":"step","title":"阶段切换","summary":"正在规划方案"},{"kind":"tool","title":"规划方案","summary":"已生成 1 套方案","tool":"plan_trip","status":"success","meta":["1 个方案"]}]}\n\n',
          'event: result\n' +
            'data: {"itinerary":{"status":"ok","plans":[{"plan_id":"plan_1","title":"平衡方案","steps":[],"selected_item_ids":[],"total_duration_minutes":240,"total_cost":220,"average_score":85}]}}\n\n',
          'event: done\n',
          'data: {"success":true}\n\n',
        ]),
      ),
    )

    await invokeStream('你好', 'thread_001', {
      onEvent(event) {
        events.push(event)
      },
    })

    expect(events).toHaveLength(5)
    expect(events[0].event).toBe('bubble')
    expect(events[1].event).toBe('message')
    expect(events[2].event).toBe('bubble')
    expect(events[3].event).toBe('result')
    expect(events[4].event).toBe('done')
    if (events[0].event !== 'bubble') {
      throw new Error('expected bubble event')
    }
    if (events[1].event !== 'message') {
      throw new Error('expected message event')
    }
    expect(events[0].data.text).toBe('正在理解你的需求')
    expect(events[1].data.text).toBe('我先帮你拆解需求')
    if (events[2].event !== 'bubble') {
      throw new Error('expected bubble event')
    }
    expect(events[2].data.phase).toBe('plan_trip')
    expect(events[2].data.entries[1].tool).toBe('plan_trip')
    expect(events[2].data.entries[1].summary).toContain('1 套方案')
    if (events[3].event !== 'result') {
      throw new Error('expected result event')
    }
    expect(events[3].data.itinerary?.plans?.[0]?.title).toBe('平衡方案')
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

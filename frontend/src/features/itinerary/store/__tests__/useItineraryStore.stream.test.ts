import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useItineraryStore } from '../useItineraryStore'

describe('useItineraryStore stream actions', () => {
  beforeEach(() => {
    localStorage.clear()
    useItineraryStore.persist.clearStorage()
    useItineraryStore.setState({
      sessions: [],
      currentSessionId: null,
      userInput: '',
      invokeStatus: 'idle',
      errorMessage: null,
    })
  })

  afterEach(() => {
    localStorage.clear()
    useItineraryStore.persist.clearStorage()
  })

  it('连续 message 事件会逐步追加当前 AI 回复内容', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_001', '初始问题')
    const userMessageId = 'local_h_1'
    store.addLocalMessage({
      id: userMessageId,
      type: 'human',
      content: '初始问题',
    })
    store.setInvokeRunning(userMessageId)

    useItineraryStore.getState().applyInvokeStreamEvent({
      event: 'message',
      data: {
        text: '正在',
      },
    })

    useItineraryStore.getState().applyInvokeStreamEvent({
      event: 'message',
      data: {
        text: '规划',
      },
    })

    const state = useItineraryStore.getState()
    expect(state.sessions[0].messages[1].type).toBe('ai')
    expect(state.sessions[0].messages[1].content).toBe('正在规划')
    expect(state.invokeStatus).toBe('running')
  })

  it('result 与 done 事件会保存最终方案并结束流式状态', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_002', '第二个问题')
    store.setInvokeRunning('local_h_2')

    useItineraryStore.getState().applyInvokeStreamEvent({
      event: 'bubble',
      data: {
        phase: 'plan_trip',
        step: 'plan_trip',
        node: 'plan_trip',
        text: '正在规划方案',
        status: 'running',
        entries: [
          {
            kind: 'step',
            title: '阶段切换',
            summary: '正在规划方案',
          },
        ],
      },
    })

    useItineraryStore.getState().applyInvokeStreamEvent({
      event: 'result',
      data: {
        itinerary: {
          status: 'ok',
          plans: [
            {
              plan_id: 'plan_1',
              title: '方案完成',
              steps: [],
              selected_item_ids: [],
              total_duration_minutes: 240,
              total_cost: 300,
              average_score: 86,
            },
          ],
        },
      },
    })

    useItineraryStore.getState().applyInvokeStreamEvent({
      event: 'done',
      data: {
        success: true,
      },
    })

    const state = useItineraryStore.getState()
    expect(state.invokeStatus).toBe('success')
    expect(state.errorMessage).toBeNull()
    expect(state.sessions[0].itinerary?.plans[0].title).toBe('方案完成')
  })

  it('bubble 事件会创建带 transientStatus 的 AI 消息', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_004', '第四个问题')
    const userMessageId = 'local_h_4'
    store.addLocalMessage({
      id: userMessageId,
      type: 'human',
      content: '第四个问题',
    })
    store.setInvokeRunning(userMessageId)

    useItineraryStore.getState().applyInvokeStreamEvent({
      event: 'bubble',
      data: {
        phase: 'plan_trip',
        step: 'plan_trip',
        node: 'plan_trip',
        text: '正在规划方案',
        status: 'running',
        entries: [
          {
            kind: 'step',
            title: '阶段切换',
            summary: '正在规划方案',
          },
          {
            kind: 'tool',
            tool: 'plan_trip',
            title: '规划方案',
            status: 'success',
            summary: '已生成 1 套方案',
            meta: ['1 个方案'],
            raw: {
              tool: 'plan_trip',
              status: 'success',
              result: {
                plans: [{ plan_id: 'plan_1', title: '亲子轻松版' }],
              },
            },
          },
        ],
      },
    })

    const state = useItineraryStore.getState()
    expect(state.sessions[0].messages).toHaveLength(2)
    expect(state.sessions[0].messages[0].type).toBe('human')
    expect(state.sessions[0].messages[1].type).toBe('ai')
    expect(state.sessions[0].messages[1].transientStatus).toBe('正在规划方案')
  })

  it('重复 bubble 条目更新同一 AI 消息的 transientStatus', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_005', '第五个问题')
    const userMessageId = 'local_h_5'
    store.addLocalMessage({
      id: userMessageId,
      type: 'human',
      content: '第五个问题',
    })
    store.setInvokeRunning(userMessageId)

    const bubbleEvent1 = {
      event: 'bubble' as const,
      data: {
        phase: 'plan_trip' as const,
        step: 'plan_trip',
        node: 'plan_trip',
        text: '正在规划方案',
        status: 'running' as const,
        entries: [],
      },
    }
    
    const bubbleEvent2 = {
      event: 'bubble' as const,
      data: {
        phase: 'plan_trip' as const,
        step: 'plan_trip',
        node: 'plan_trip',
        text: '正在生成更多方案',
        status: 'running' as const,
        entries: [],
      },
    }

    useItineraryStore.getState().applyInvokeStreamEvent(bubbleEvent1)
    useItineraryStore.getState().applyInvokeStreamEvent(bubbleEvent2)

    const state = useItineraryStore.getState()
    expect(state.sessions[0].messages).toHaveLength(2)
    expect(state.sessions[0].messages[1].transientStatus).toBe('正在生成更多方案')
  })

  it('error 事件会写入错误并清空临时状态', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_003', '第三个问题')
    store.setInvokeRunning('local_h_3')

    useItineraryStore.getState().applyInvokeStreamEvent({
      event: 'bubble',
      data: {
        phase: 'search_candidates',
        step: 'search_candidates',
        node: 'search_candidates',
        text: '正在搜索',
        status: 'running',
        entries: [
          {
            kind: 'step',
            title: '阶段切换',
            summary: '正在搜索',
          },
        ],
      },
    })

    useItineraryStore.getState().applyInvokeStreamEvent({
      event: 'error',
      data: {
        message: 'stream failed',
      },
    })

    const state = useItineraryStore.getState()
    expect(state.invokeStatus).toBe('error')
    expect(state.errorMessage).toBe('stream failed')
  })
})

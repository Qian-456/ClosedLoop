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
      currentProcessBubble: null,
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
    expect(state.currentProcessBubble?.text).toBe('正在思考')
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
    expect(state.currentProcessBubble).toBeNull()
    expect(state.sessions[0].itinerary?.plans[0].title).toBe('方案完成')
    expect(state.sessions[0].processHistory).toHaveLength(1)
    expect(state.sessions[0].processHistory?.[0].text).toBe('已完成规划')
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
    expect(state.currentProcessBubble?.entries).toHaveLength(2)
    expect(state.currentProcessBubble?.entries[1].title).toBe('规划方案')
    expect(state.currentProcessBubble?.entries[1].summary).toContain('已生成 1 套方案')
    expect(state.currentProcessBubble?.entries[1].tool).toBe('plan_trip')
    expect(state.currentProcessBubble?.phase).toBe('plan_trip')
    expect(state.currentProcessBubble?.text).toBe('正在规划方案')
    expect(state.sessions[0].messages).toHaveLength(2)
    expect(state.sessions[0].messages[0].type).toBe('human')
    expect(state.sessions[0].messages[1].type).toBe('ai')
    expect(state.sessions[0].messages[1].transientStatus).toBe('正在规划方案')
  })

  it('重复 bubble 条目不会重复追加过程详情', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_005', '第五个问题')
    const userMessageId = 'local_h_5'
    store.addLocalMessage({
      id: userMessageId,
      type: 'human',
      content: '第五个问题',
    })
    store.setInvokeRunning(userMessageId)

    const bubbleEvent = {
      event: 'bubble' as const,
      data: {
        phase: 'plan_trip' as const,
        step: 'plan_trip',
        node: 'plan_trip',
        text: '正在规划方案',
        status: 'running' as const,
        entries: [
          {
            kind: 'step' as const,
            title: '阶段切换',
            summary: '正在规划方案',
          },
          {
            kind: 'tool' as const,
            tool: 'plan_trip',
            title: '规划方案',
            status: 'success' as const,
            summary: '已生成 1 套方案',
            meta: ['预算 320 元', '总时长 240 分钟'],
            raw: {
              tool: 'plan_trip',
              status: 'success',
              result: {
                plans: [
                  {
                    plan_id: 'plan_1',
                    title: '亲子轻松版',
                    total_cost: 320,
                    total_duration_minutes: 240,
                  },
                ],
              },
            },
          },
        ],
      },
    }

    useItineraryStore.getState().applyInvokeStreamEvent(bubbleEvent)
    useItineraryStore.getState().applyInvokeStreamEvent(bubbleEvent)

    const state = useItineraryStore.getState()
    expect(state.currentProcessBubble?.entries).toHaveLength(2)
    expect(state.currentProcessBubble?.entries[1].meta).toContain('预算 320 元')
    expect(state.currentProcessBubble?.entries[1].meta).toContain('总时长 240 分钟')
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
        text: '正在召回候选地点',
        status: 'running',
        entries: [
          {
            kind: 'step',
            title: '阶段切换',
            summary: '正在召回候选地点',
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
    expect(state.currentProcessBubble).toBeNull()
    expect(state.sessions[0].processHistory?.[0].status).toBe('failed')
    expect(state.sessions[0].processHistory?.[0].text).toBe('处理失败，请稍后重试')
  })
})

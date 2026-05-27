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

  it('连续 state 事件会覆盖当前会话消息', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_001', '初始问题')
    store.addLocalMessage({
      id: 'local_h_1',
      type: 'human',
      content: '初始问题',
    })
    store.setInvokeRunning()

    useItineraryStore.getState().applyInvokeStreamState({
      user_input: '初始问题',
      messages: [
        { id: 'msg_h_1', type: 'human', content: '初始问题' },
        { id: 'msg_ai_1', type: 'ai', content: '正在规划' },
      ],
    })

    useItineraryStore.getState().applyInvokeStreamState({
      user_input: '初始问题',
      messages: [
        { id: 'msg_h_1', type: 'human', content: '初始问题' },
        { id: 'msg_ai_2', type: 'ai', content: '最终结果' },
      ],
    })

    const state = useItineraryStore.getState()
    expect(state.sessions[0].messages).toEqual([
      { id: 'msg_h_1', type: 'human', content: '初始问题' },
      { id: 'msg_ai_2', type: 'ai', content: '最终结果' },
    ])
    expect(state.invokeStatus).toBe('running')
  })

  it('done 事件会把状态落为 success，并保留最终消息', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_002', '第二个问题')
    store.setInvokeRunning()

    useItineraryStore.getState().finishInvokeStream({
      user_input: '第二个问题',
      messages: [
        { id: 'msg_h_2', type: 'human', content: '第二个问题' },
        { id: 'msg_ai_3', type: 'ai', content: '方案完成' },
      ],
    })

    const state = useItineraryStore.getState()
    expect(state.invokeStatus).toBe('success')
    expect(state.errorMessage).toBeNull()
    expect(state.sessions[0].messages[1].content).toBe('方案完成')
  })
})

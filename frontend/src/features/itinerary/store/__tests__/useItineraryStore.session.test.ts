import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useItineraryStore } from '../useItineraryStore'

describe('useItineraryStore session actions', () => {
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

  it('同一个 sessionId 再次 startSession 时不重复插入', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_same', '第一次标题')
    store.startSession('thread_same', '第二次标题')

    const state = useItineraryStore.getState()
    expect(state.sessions).toHaveLength(1)
    expect(state.currentSessionId).toBe('thread_same')
    expect(state.sessions[0].title).toBe('第二次标题')
  })

  it('不同 sessionId 的真实新会话仍然正常新增', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_001', '问题一')
    store.startSession('thread_002', '问题二')

    const state = useItineraryStore.getState()
    expect(state.sessions).toHaveLength(2)
    expect(state.sessions[0].id).toBe('thread_002')
    expect(state.sessions[1].id).toBe('thread_001')
  })

  it('默认空标题会话只保留单实例语义', () => {
    const store = useItineraryStore.getState()

    store.startSession('thread_empty_1')
    store.startSession('thread_empty_2')

    const state = useItineraryStore.getState()
    expect(state.sessions).toHaveLength(1)
    expect(state.currentSessionId).toBe('thread_empty_1')
    expect(state.sessions[0].title).toBe('新对话')
  })
})

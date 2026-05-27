import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { ChatView } from '../ChatView'
import { useItineraryStore } from '../../store/useItineraryStore'

describe('ChatView ProcessBubble', () => {
  beforeEach(() => {
    localStorage.clear()
    useItineraryStore.persist.clearStorage()
    useItineraryStore.setState({
      sessions: [],
      currentSessionId: null,
      userInput: '',
      invokeStatus: 'idle',
      errorMessage: null,
      currentStatus: null,
      currentProcessBubble: null,
    })
  })

  it('当 AIMessage 尚未出现时，在用户消息下方显示默认过程气泡', () => {
    useItineraryStore.setState({
      sessions: [
        {
          id: 'thread_001',
          title: '测试会话',
          messages: [
            {
              id: 'human_1',
              type: 'human',
              content: '帮我规划一下今天下午的安排',
            },
          ],
          itinerary: null,
          confirmation: null,
          processHistory: [],
          updatedAt: Date.now(),
        },
      ],
      currentSessionId: 'thread_001',
      invokeStatus: 'running',
      currentProcessBubble: {
        id: 'process_1',
        sessionId: 'thread_001',
        relatedUserMessageId: 'human_1',
        phase: 'bootstrap',
        text: '正在理解用户需求',
        expanded: false,
        status: 'running',
        processItems: [],
      },
    })

    render(<ChatView />)

    expect(screen.getByText('帮我规划一下今天下午的安排')).toBeInTheDocument()
    expect(screen.getByText('正在理解用户需求')).toBeInTheDocument()
  })

  it('完成后的过程气泡会保留在聊天流里，并与 AI 回复同时可见', () => {
    useItineraryStore.setState({
      sessions: [
        {
          id: 'thread_002',
          title: '历史会话',
          messages: [
            {
              id: 'human_2',
              type: 'human',
              content: '今天下午想带孩子出去玩',
            },
            {
              id: 'ai_2',
              type: 'ai',
              content: '我已经为你整理好一套亲子友好的下午行程。',
            },
          ],
          itinerary: null,
          confirmation: null,
          processHistory: [
            {
              id: 'process_done_2',
              sessionId: 'thread_002',
              relatedUserMessageId: 'human_2',
              phase: 'done',
              text: '已完成规划',
              expanded: false,
              status: 'success',
              processItems: [
                {
                  tool: 'plan_trip',
                  status: 'success',
                  summary: '已生成 1 套方案',
                },
              ],
            },
          ],
          updatedAt: Date.now(),
        },
      ],
      currentSessionId: 'thread_002',
      invokeStatus: 'success',
      currentProcessBubble: null,
    })

    render(<ChatView />)

    expect(screen.getByText('今天下午想带孩子出去玩')).toBeInTheDocument()
    expect(screen.getByText('已完成规划')).toBeInTheDocument()
    expect(screen.getByText('我已经为你整理好一套亲子友好的下午行程。')).toBeInTheDocument()
  })
})

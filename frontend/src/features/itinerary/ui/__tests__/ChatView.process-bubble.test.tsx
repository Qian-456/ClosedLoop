import { beforeEach, describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

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
        entries: [],
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
              entries: [
                {
                  kind: 'tool',
                  tool: 'plan_trip',
                  status: 'success',
                  title: '规划方案',
                  summary: '已生成 1 套方案',
                  meta: ['1 个方案'],
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

  it('会同时保留过程型 AI 文案和最终总结消息', () => {
    useItineraryStore.setState({
      sessions: [
        {
          id: 'thread_003',
          title: '规划中会话',
          messages: [
            {
              id: 'human_3',
              type: 'human',
              content: '帮我规划亲子行程',
            },
            {
              id: 'ai_process_3',
              type: 'ai',
              content: '好的！我先提取您的需求，然后调用规划工具。',
            },
            {
              id: 'ai_final_3',
              type: 'ai',
              content: '为您规划好了！以下是方案 A 的详细行程。',
            },
          ],
          itinerary: null,
          confirmation: null,
          processHistory: [
            {
              id: 'process_done_3',
              sessionId: 'thread_003',
              relatedUserMessageId: 'human_3',
              phase: 'done',
              text: '已完成规划',
              expanded: false,
              status: 'success',
              entries: [
                {
                  kind: 'tool',
                  tool: 'plan_trip',
                  status: 'success',
                  title: '规划方案',
                  summary: '已生成 1 套方案',
                  meta: ['预算 436.99 元', '总时长 340 分钟'],
                },
              ],
            },
          ],
          updatedAt: Date.now(),
        },
      ],
      currentSessionId: 'thread_003',
      invokeStatus: 'success',
      currentProcessBubble: null,
    })

    render(<ChatView />)

    expect(screen.getByText('好的！我先提取您的需求，然后调用规划工具。')).toBeInTheDocument()
    expect(screen.getByText('已完成规划')).toBeInTheDocument()
    expect(screen.getByText('为您规划好了！以下是方案 A 的详细行程。')).toBeInTheDocument()
  })

  it('展开 bubble 后会显示按节点阶段分组的过程条目', () => {
    useItineraryStore.setState({
      sessions: [
        {
          id: 'thread_004',
          title: '节点过程会话',
          messages: [
            {
              id: 'human_4',
              type: 'human',
              content: '帮我规划今晚的安排',
            },
          ],
          itinerary: null,
          confirmation: null,
          processHistory: [
            {
              id: 'process_done_4',
              sessionId: 'thread_004',
              relatedUserMessageId: 'human_4',
              phase: 'done',
              text: '已完成规划',
              expanded: false,
              status: 'success',
              entries: [
                {
                  kind: 'step',
                  title: '阶段切换',
                  summary: '正在规划方案',
                },
                {
                  kind: 'tool',
                  tool: 'plan_trip',
                  status: 'success',
                  title: '规划方案',
                  summary: '已生成 1 套方案',
                  meta: ['预算 320 元', '总时长 240 分钟'],
                },
              ],
            },
          ],
          updatedAt: Date.now(),
        },
      ],
      currentSessionId: 'thread_004',
      invokeStatus: 'success',
      currentProcessBubble: null,
    })

    render(<ChatView />)

    fireEvent.click(screen.getByText('已完成规划'))

    expect(screen.getByText('阶段切换')).toBeInTheDocument()
    expect(screen.getByText('正在规划方案')).toBeInTheDocument()
    expect(screen.getByText('规划方案')).toBeInTheDocument()
    expect(screen.getByText('预算 320 元')).toBeInTheDocument()
    expect(screen.getByText('总时长 240 分钟')).toBeInTheDocument()
  })
})

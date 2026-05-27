import { describe, expect, it } from 'vitest'

import { isProcessLikeAiMessage, shouldRenderChatMessage } from '../display'
import type { Message, ProcessBubbleRecord, Session } from '../types'

function createBubble(text = '正在规划方案'): ProcessBubbleRecord {
  return {
    id: 'process_1',
    sessionId: 'thread_001',
    relatedUserMessageId: 'human_1',
    phase: 'plan_trip',
    text,
    expanded: false,
    status: 'running',
    entries: [],
  }
}

function createSession(messages: Message[], bubble?: ProcessBubbleRecord): Session {
  return {
    id: 'thread_001',
    title: '测试会话',
    messages,
    itinerary: null,
    confirmation: null,
    processHistory: bubble ? [bubble] : [],
    updatedAt: Date.now(),
  }
}

describe('display message filters', () => {
  it('存在过程气泡时，不再把 AI 文案识别为需隐藏的过程消息', () => {
    const message: Message = {
      id: 'ai_1',
      type: 'ai',
      content: '好的！我先提取您的需求，然后调用规划工具。',
    }

    expect(isProcessLikeAiMessage(message, createBubble())).toBe(false)
  })

  it('存在过程气泡时，最终总结类 AI 文案仍然不被标记为过程文案', () => {
    const message: Message = {
      id: 'ai_2',
      type: 'ai',
      content: '为您规划好了！以下是方案 A 的详细行程。',
    }

    expect(isProcessLikeAiMessage(message, createBubble())).toBe(false)
  })

  it('存在过程气泡时，仍然保留过程型 AI 文案', () => {
    const humanMessage: Message = {
      id: 'human_1',
      type: 'human',
      content: '今天下午一家三口出去玩',
    }
    const aiMessage: Message = {
      id: 'ai_3',
      type: 'ai',
      content: '开始规划！我会先调用规划工具。',
    }
    const bubble = createBubble()
    const session = createSession([humanMessage, aiMessage], bubble)

    expect(
      shouldRenderChatMessage(aiMessage, {
        session,
        relatedProcessBubble: bubble,
      }),
    ).toBe(true)
  })

  it('存在过程气泡时，会保留最终总结类 AI 文案', () => {
    const humanMessage: Message = {
      id: 'human_1',
      type: 'human',
      content: '今天下午一家三口出去玩',
    }
    const aiMessage: Message = {
      id: 'ai_4',
      type: 'ai',
      content: '为您规划好了！以下是方案 A 的详细行程。',
    }
    const bubble = createBubble('已完成规划')
    const session = createSession([humanMessage, aiMessage], bubble)

    expect(
      shouldRenderChatMessage(aiMessage, {
        session,
        relatedProcessBubble: bubble,
      }),
    ).toBe(true)
  })

  it('没有过程气泡时，不隐藏普通 AI 文案', () => {
    const aiMessage: Message = {
      id: 'ai_5',
      type: 'ai',
      content: '好的！我先提取您的需求，然后调用规划工具。',
    }
    const session = createSession([aiMessage])

    expect(
      shouldRenderChatMessage(aiMessage, {
        session,
        relatedProcessBubble: null,
      }),
    ).toBe(true)
  })
})

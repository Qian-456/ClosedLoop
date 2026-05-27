import { describe, expect, it } from 'vitest'

import { shouldRenderChatMessage } from '../display'
import type { Message, Session } from '../types'

function createSession(messages: Message[]): Session {
  return {
    id: 'thread_001',
    title: '测试会话',
    messages,
    itinerary: null,
    confirmation: null,
    updatedAt: Date.now(),
  }
}

describe('display message filters', () => {
  it('保留普通 AI 文案', () => {
    const aiMessage: Message = {
      id: 'ai_1',
      type: 'ai',
      content: '好的！我先提取您的需求，然后调用规划工具。',
    }
    const session = createSession([aiMessage])

    expect(
      shouldRenderChatMessage(aiMessage, {
        session,
      }),
    ).toBe(true)
  })

  it('保留最终总结类 AI 文案', () => {
    const aiMessage: Message = {
      id: 'ai_2',
      type: 'ai',
      content: '为您规划好了！以下是方案 A 的详细行程。',
    }
    const session = createSession([aiMessage])

    expect(
      shouldRenderChatMessage(aiMessage, {
        session,
      }),
    ).toBe(true)
  })
})

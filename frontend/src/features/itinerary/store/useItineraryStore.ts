import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  ClosedLoopState,
  Session,
  Message,
  InvokeStreamEvent,
} from '../model/types'
import type { MockPaymentCommitResponse } from '../api/invoke'

export type InvokeStatus = 'idle' | 'running' | 'success' | 'error'

type ItineraryStore = {
  sessions: Session[]
  currentSessionId: string | null
  
  userInput: string
  invokeStatus: InvokeStatus
  errorMessage: string | null

  setUserInput: (v: string) => void
  startSession: (sessionId: string, initialMessage?: string) => void
  switchSession: (sessionId: string) => void
  deleteSession: (sessionId: string) => void
  
  addLocalMessage: (message: Message) => void
  setInvokeRunning: (relatedUserMessageId?: string) => void
  setInvokeSuccess: (state: ClosedLoopState) => void
  applyInvokeStreamEvent: (event: InvokeStreamEvent) => void
  applyPaymentCommit: (result: MockPaymentCommitResponse) => void
  setInvokeError: (message: string) => void
  reset: () => void
}

function mergeApiStateIntoSessions(
  sessions: Session[],
  currentSessionId: string | null,
  apiState?: ClosedLoopState,
): Session[] {
  if (!currentSessionId) {
    return sessions
  }

  return sessions.map((session) => {
    if (session.id !== currentSessionId) {
      return session
    }

    return {
      ...session,
      messages:
        apiState?.messages && apiState.messages.length > 0 ? apiState.messages : session.messages,
      itinerary: apiState?.itinerary ?? session.itinerary ?? null,
      confirmation: apiState?.confirmation ?? session.confirmation ?? null,
      updatedAt: Date.now(),
    }
  })
}

function updateCurrentSession(
  sessions: Session[],
  currentSessionId: string | null,
  updater: (session: Session) => Session,
): Session[] {
  if (!currentSessionId) {
    return sessions
  }

  return sessions.map((session) => {
    if (session.id !== currentSessionId) {
      return session
    }
    return updater(session)
  })
}

function appendAssistantChunk(messages: Message[], text: string, node?: string): Message[] {
  if (!text) {
    return messages
  }

  const nextMessages = [...messages]
  const lastMessage = nextMessages[nextMessages.length - 1]
  
  if (lastMessage?.type === 'ai' && (lastMessage.node === node || !lastMessage.node)) {
    nextMessages[nextMessages.length - 1] = {
      ...lastMessage,
      content: `${typeof lastMessage.content === 'string' ? lastMessage.content : ''}${text}`,
      node: node || lastMessage.node,
    }
    return nextMessages
  }

  nextMessages.push({
    id: `ai_stream_${Date.now()}`,
    type: 'ai',
    content: text,
    node: node,
  })
  return nextMessages
}

function isDefaultEmptySession(session: Session): boolean {
  return session.title === '新对话' && session.messages.length === 0
}

export const useItineraryStore = create<ItineraryStore>()(
  persist(
    (set) => ({
      sessions: [],
      currentSessionId: null,
      
      userInput: '',
      invokeStatus: 'idle',
      errorMessage: null,
      
      setUserInput: (v) => set({ userInput: v }),
      
      startSession: (sessionId, initialMessage) => set((state) => {
        const nextTitle = initialMessage ? initialMessage.slice(0, 20) : '新对话'
        const existingSession = state.sessions.find((session) => session.id === sessionId)
        if (existingSession) {
          return {
            sessions: state.sessions.map((session) => {
              if (session.id !== sessionId) {
                return session
              }

              return {
                ...session,
                title: nextTitle,
                updatedAt: Date.now(),
              }
            }),
            currentSessionId: sessionId,
            userInput: '',
            invokeStatus: 'idle',
            errorMessage: null,
          }
        }

        if (!initialMessage) {
          const existingEmptySession = state.sessions.find(isDefaultEmptySession)
          if (existingEmptySession) {
            return {
              currentSessionId: existingEmptySession.id,
              userInput: '',
              invokeStatus: 'idle',
              errorMessage: null,
            }
          }
        }

        const newSession: Session = {
          id: sessionId,
          title: nextTitle,
          messages: [],
          itinerary: null,
          confirmation: null,
          updatedAt: Date.now()
        }
        return {
          sessions: [newSession, ...state.sessions],
          currentSessionId: sessionId,
          userInput: '',
          invokeStatus: 'idle',
          errorMessage: null,
        }
      }),
      
      switchSession: (sessionId) => set({
        currentSessionId: sessionId,
        userInput: '',
        invokeStatus: 'idle',
        errorMessage: null,
      }),

      deleteSession: (sessionId) => set((state) => {
        const sessions = state.sessions.filter(s => s.id !== sessionId)
        return {
          sessions,
          currentSessionId: state.currentSessionId === sessionId ? (sessions[0]?.id || null) : state.currentSessionId
        }
      }),

      addLocalMessage: (message) => set((state) => {
        if (!state.currentSessionId) return state
        return {
          sessions: state.sessions.map(s => {
            if (s.id === state.currentSessionId) {
              return {
                ...s,
                messages: [...s.messages, message],
                updatedAt: Date.now()
              }
            }
            return s
          })
        }
      }),

      setInvokeRunning: () => set((state) => {
        if (!state.currentSessionId) {
          return {
            invokeStatus: 'running',
            errorMessage: null,
          }
        }

        return {
          invokeStatus: 'running',
          errorMessage: null,
        }
      }),
      
      setInvokeSuccess: (apiState) => set((state) => {
        return {
          invokeStatus: 'success',
          errorMessage: null,
          sessions: mergeApiStateIntoSessions(state.sessions, state.currentSessionId, apiState),
        }
      }),

      applyInvokeStreamEvent: (event) => set((state) => {
        if (!state.currentSessionId) {
          return state
        }

        if (event.event === 'message') {
          return {
            invokeStatus: 'running',
            errorMessage: null,
            sessions: updateCurrentSession(state.sessions, state.currentSessionId, (session) => ({
              ...session,
              messages: appendAssistantChunk(session.messages, event.data.text, event.data.node),
              updatedAt: Date.now(),
            })),
          }
        }

        if (event.event === 'bubble') {
          return {
            invokeStatus: 'running',
            errorMessage: null,
            sessions: updateCurrentSession(state.sessions, state.currentSessionId, (session) => {
              const nextMessages = [...session.messages]
              const lastMessage = nextMessages[nextMessages.length - 1]
              const nodeOrPhase = event.data.node || event.data.phase

              if (lastMessage?.type === 'ai' && (lastMessage.node === nodeOrPhase || !lastMessage.node)) {
                nextMessages[nextMessages.length - 1] = {
                  ...lastMessage,
                  node: nodeOrPhase,
                  transientStatus: event.data.text,
                }
              } else if (lastMessage?.type === 'ai' && !lastMessage.content) {
                nextMessages[nextMessages.length - 1] = {
                  ...lastMessage,
                  node: nodeOrPhase,
                  transientStatus: event.data.text,
                }
              } else {
                nextMessages.push({
                  id: `ai_stream_${Date.now()}_${Math.random()}`,
                  type: 'ai',
                  content: '',
                  node: nodeOrPhase,
                  transientStatus: event.data.text,
                })
              }

              return {
                ...session,
                messages: nextMessages,
                updatedAt: Date.now(),
              }
            }),
          }
        }

        if (event.event === 'result') {
          return {
            invokeStatus: 'running',
            errorMessage: null,
            sessions: updateCurrentSession(state.sessions, state.currentSessionId, (session) => ({
              ...session,
              itinerary: event.data.itinerary ?? session.itinerary ?? null,
              confirmation: event.data.confirmation ?? session.confirmation ?? null,
              updatedAt: Date.now(),
            })),
          }
        }

        if (event.event === 'done') {
          return {
            invokeStatus: event.data.success ? 'success' : 'error',
            errorMessage: event.data.success ? null : state.errorMessage,
          }
        }

        return {
          invokeStatus: 'error',
          errorMessage: event.data.message,
        }
      }),

      applyPaymentCommit: (result) => set((state) => {
        return {
          sessions: updateCurrentSession(state.sessions, state.currentSessionId, (session) => ({
            ...session,
            confirmation: {
              ...(session.confirmation ?? { status: 'executed' }),
              status: result.commit_status === 'success' ? 'executed' : 'failed',
              execution_id: result.execution_id,
              payment_status: result.payment_status,
              commit_status: result.commit_status,
              reason: result.message,
              execution_summary: {
                ...(session.confirmation?.execution_summary ?? {}),
                execution_id: result.commit_execution_id ?? result.execution_id,
                items: result.items ?? [],
                failures: (result.failures ?? []).filter(
                  (item): item is { item_id?: string; item_name?: string; item_type?: string } =>
                    typeof item === 'object' && item !== null,
                ),
                replacements: session.confirmation?.execution_summary?.replacements ?? [],
              },
            },
            updatedAt: Date.now(),
          })),
        }
      }),
      
      setInvokeError: (message) => set(() => {
        return {
          invokeStatus: 'error',
          errorMessage: message,
        }
      }),
      
      reset: () => set({
        currentSessionId: null,
        userInput: '',
        invokeStatus: 'idle',
        errorMessage: null,
      }),
    }),
    {
      name: 'closedloop-sessions',
      partialize: (state) => ({ sessions: state.sessions, currentSessionId: state.currentSessionId }),
    }
  )
)

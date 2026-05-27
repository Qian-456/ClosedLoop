import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  BubbleEntry,
  ClosedLoopState,
  Session,
  Message,
  InvokeStreamEvent,
  ProcessBubblePhase,
  ProcessBubbleRecord,
} from '../model/types'

export type InvokeStatus = 'idle' | 'running' | 'success' | 'error'

type ItineraryStore = {
  sessions: Session[]
  currentSessionId: string | null
  
  userInput: string
  invokeStatus: InvokeStatus
  errorMessage: string | null
  currentProcessBubble: ProcessBubbleRecord | null

  setUserInput: (v: string) => void
  startSession: (sessionId: string, initialMessage?: string) => void
  switchSession: (sessionId: string) => void
  deleteSession: (sessionId: string) => void
  
  addLocalMessage: (message: Message) => void
  setInvokeRunning: (relatedUserMessageId?: string) => void
  setInvokeSuccess: (state: ClosedLoopState) => void
  applyInvokeStreamEvent: (event: InvokeStreamEvent) => void
  setInvokeError: (message: string) => void
  toggleProcessBubble: (bubbleId?: string) => void
  updateCommuteMode: (
    planId: string,
    commuteItemId: string,
    mode: 'walking' | 'taxi' | 'driving',
  ) => void
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
      processHistory: session.processHistory ?? [],
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

function getLatestHumanMessageId(session: Session | undefined): string | undefined {
  if (!session) {
    return undefined
  }
  const reversed = [...session.messages].reverse()
  const latestHuman = reversed.find((message) => message.type === 'human' && typeof message.id === 'string')
  return latestHuman?.id
}

function createProcessBubble(
  sessionId: string,
  relatedUserMessageId?: string,
): ProcessBubbleRecord {
  return {
    id: `process_${Date.now()}`,
    sessionId,
    relatedUserMessageId,
    phase: 'bootstrap',
    text: '正在思考',
    expanded: false,
    status: 'running',
    entries: [],
  }
}

function appendBubbleEntries(entries: BubbleEntry[], nextEntries: BubbleEntry[]): BubbleEntry[] {
  const merged = [...entries]
  for (const nextEntry of nextEntries) {
    const nextSignature = JSON.stringify(nextEntry)
    if (merged.some((item) => JSON.stringify(item) === nextSignature)) {
      continue
    }
    merged.push(nextEntry)
  }
  return merged
}

function mapPhaseText(phase: ProcessBubblePhase): string {
  switch (phase) {
    case 'search_candidates':
      return '正在召回候选地点'
    case 'plan_trip':
      return '正在规划方案'
    case 'generate_alternative_plans':
      return '正在生成更多方案'
    case 'adjust_plan_item':
      return '正在调整方案'
    case 'transfer_to_execute':
      return '正在切换到执行确认'
    case 'confirm_trip':
      return '正在整理执行结果'
    case 'done':
      return '已完成规划'
    case 'error':
      return '处理失败，请稍后重试'
    case 'bootstrap':
    default:
      return '正在思考'
  }
}

function archiveProcessBubbleIntoSession(
  sessions: Session[],
  currentSessionId: string | null,
  bubble: ProcessBubbleRecord,
): Session[] {
  return updateCurrentSession(sessions, currentSessionId, (session) => ({
    ...session,
    processHistory: [...(session.processHistory ?? []), bubble],
    updatedAt: Date.now(),
  }))
}

function toggleProcessBubbleInSession(
  sessions: Session[],
  currentSessionId: string | null,
  bubbleId: string,
): Session[] {
  return updateCurrentSession(sessions, currentSessionId, (session) => ({
    ...session,
    processHistory: (session.processHistory ?? []).map((bubble) =>
      bubble.id === bubbleId ? { ...bubble, expanded: !bubble.expanded } : bubble,
    ),
  }))
}

function isDefaultEmptySession(session: Session): boolean {
  return session.title === '新对话' && session.messages.length === 0
}

export const useItineraryStore = create<ItineraryStore>()(
  persist(
    (set, _get) => ({
      sessions: [],
      currentSessionId: null,
      
      userInput: '',
      invokeStatus: 'idle',
      errorMessage: null,
      currentProcessBubble: null,
      
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
                processHistory: session.processHistory ?? [],
                updatedAt: Date.now(),
              }
            }),
            currentSessionId: sessionId,
            userInput: '',
            invokeStatus: 'idle',
            errorMessage: null,
            currentProcessBubble: null,
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
              currentProcessBubble: null,
            }
          }
        }

        const newSession: Session = {
          id: sessionId,
          title: nextTitle,
          messages: [],
          itinerary: null,
          confirmation: null,
          processHistory: [],
          updatedAt: Date.now()
        }
        return {
          sessions: [newSession, ...state.sessions],
          currentSessionId: sessionId,
          userInput: '',
          invokeStatus: 'idle',
          errorMessage: null,
          currentProcessBubble: null,
        }
      }),
      
      switchSession: (sessionId) => set({
        currentSessionId: sessionId,
        userInput: '',
        invokeStatus: 'idle',
        errorMessage: null,
        currentProcessBubble: null,
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

      setInvokeRunning: (relatedUserMessageId) => set((state) => {
        const sessionId = state.currentSessionId
        if (!sessionId) {
          return {
            invokeStatus: 'running',
            errorMessage: null,
            currentProcessBubble: null,
          }
        }

        const currentSession = state.sessions.find((session) => session.id === sessionId)
        return {
          invokeStatus: 'running',
          errorMessage: null,
          currentProcessBubble: createProcessBubble(
            sessionId,
            relatedUserMessageId ?? getLatestHumanMessageId(currentSession),
          ),
        }
      }),
      
      setInvokeSuccess: (apiState) => set((state) => {
        return {
          invokeStatus: 'success',
          errorMessage: null,
          currentProcessBubble: null,
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
          const currentSession = state.sessions.find((session) => session.id === state.currentSessionId)
          const currentBubble =
            state.currentProcessBubble ??
            createProcessBubble(state.currentSessionId, getLatestHumanMessageId(currentSession))
            
          return {
            invokeStatus: 'running',
            errorMessage: null,
            currentProcessBubble: {
              ...currentBubble,
              phase: event.data.phase,
              text: event.data.text,
              status: event.data.status ?? currentBubble.status,
              entries: appendBubbleEntries(currentBubble.entries, event.data.entries),
            },
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
          const finishedBubble: ProcessBubbleRecord | null = state.currentProcessBubble
            ? {
                ...state.currentProcessBubble,
                phase: event.data.success ? 'done' : 'error',
                text: event.data.success ? mapPhaseText('done') : mapPhaseText('error'),
                status: event.data.success ? 'success' : 'failed',
              }
            : null
          return {
            invokeStatus: event.data.success ? 'success' : 'error',
            errorMessage: event.data.success ? null : state.errorMessage,
            currentProcessBubble: null,
            sessions: finishedBubble
              ? archiveProcessBubbleIntoSession(state.sessions, state.currentSessionId, finishedBubble)
              : state.sessions,
          }
        }

        const failedBubble: ProcessBubbleRecord | null = state.currentProcessBubble
          ? {
              ...state.currentProcessBubble,
              phase: 'error',
              text: mapPhaseText('error'),
              status: 'failed',
            }
          : null
        return {
          invokeStatus: 'error',
          errorMessage: event.data.message,
          currentProcessBubble: null,
          sessions: failedBubble
            ? archiveProcessBubbleIntoSession(state.sessions, state.currentSessionId, failedBubble)
            : state.sessions,
        }
      }),
      
      setInvokeError: (message) => set((state) => {
        const failedBubble: ProcessBubbleRecord | null = state.currentProcessBubble
          ? {
              ...state.currentProcessBubble,
              phase: 'error',
              text: mapPhaseText('error'),
              status: 'failed',
            }
          : null

        return {
          invokeStatus: 'error',
          errorMessage: message,
          currentProcessBubble: null,
          sessions: failedBubble
            ? archiveProcessBubbleIntoSession(state.sessions, state.currentSessionId, failedBubble)
            : state.sessions,
        }
      }),

      toggleProcessBubble: (bubbleId) => set((state) => {
        if (bubbleId && state.currentProcessBubble?.id === bubbleId) {
          return {
            currentProcessBubble: {
              ...state.currentProcessBubble,
              expanded: !state.currentProcessBubble.expanded,
            },
          }
        }

        if (!bubbleId && state.currentProcessBubble) {
          return {
            currentProcessBubble: {
              ...state.currentProcessBubble,
              expanded: !state.currentProcessBubble.expanded,
            },
          }
        }

        if (!bubbleId) {
          return state
        }

        return {
          sessions: toggleProcessBubbleInSession(state.sessions, state.currentSessionId, bubbleId),
        }
      }),
      
      updateCommuteMode: (_planId, _commuteItemId, _mode) => {
        // Since we removed state.itinerary from the root level and it's inside messages or not needed,
        // we'll leave this empty or minimal for now. If needed, we can update it later.
        console.warn('updateCommuteMode is deprecated in chat interface mode.')
      },
      
      reset: () => set({
        currentSessionId: null,
        userInput: '',
        invokeStatus: 'idle',
        errorMessage: null,
        currentProcessBubble: null,
      }),
    }),
    {
      name: 'closedloop-sessions',
      partialize: (state) => ({ sessions: state.sessions, currentSessionId: state.currentSessionId }),
    }
  )
)

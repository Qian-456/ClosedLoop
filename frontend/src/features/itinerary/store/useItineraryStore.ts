import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ClosedLoopState, Session, Message } from '../model/types'

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
  setInvokeRunning: () => void
  setInvokeSuccess: (state: ClosedLoopState) => void
  applyInvokeStreamState: (state: ClosedLoopState) => void
  finishInvokeStream: (state?: ClosedLoopState) => void
  setInvokeError: (message: string) => void
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

    const updatedMessages =
      apiState?.messages && apiState.messages.length > 0 ? apiState.messages : session.messages

    return {
      ...session,
      messages: updatedMessages,
      updatedAt: Date.now(),
    }
  })
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

      setInvokeRunning: () => set({ invokeStatus: 'running', errorMessage: null }),
      
      setInvokeSuccess: (apiState) => set((state) => {
        return {
          invokeStatus: 'success',
          errorMessage: null,
          sessions: mergeApiStateIntoSessions(state.sessions, state.currentSessionId, apiState),
        }
      }),

      applyInvokeStreamState: (apiState) => set((state) => ({
        invokeStatus: 'running',
        errorMessage: null,
        sessions: mergeApiStateIntoSessions(state.sessions, state.currentSessionId, apiState),
      })),

      finishInvokeStream: (apiState) => set((state) => ({
        invokeStatus: 'success',
        errorMessage: null,
        sessions: mergeApiStateIntoSessions(state.sessions, state.currentSessionId, apiState),
      })),
      
      setInvokeError: (message) => set({ invokeStatus: 'error', errorMessage: message }),
      
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
      }),
    }),
    {
      name: 'closedloop-sessions',
      partialize: (state) => ({ sessions: state.sessions, currentSessionId: state.currentSessionId }),
    }
  )
)

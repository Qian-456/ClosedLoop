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
  setInvokeError: (message: string) => void
  updateCommuteMode: (
    planId: string,
    commuteItemId: string,
    mode: 'walking' | 'taxi' | 'driving',
  ) => void
  reset: () => void
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
        const newSession: Session = {
          id: sessionId,
          title: initialMessage ? initialMessage.slice(0, 20) : '新对话',
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
        if (!state.currentSessionId) return state
        return {
          invokeStatus: 'success',
          errorMessage: null,
          sessions: state.sessions.map(s => {
            if (s.id === state.currentSessionId) {
              // If backend returned messages, use them, otherwise we just keep local ones.
              // Wait, LangChain's state.messages might have the full history.
              // Let's assume if state.messages exists, it's the full history.
              const updatedMessages = apiState.messages && apiState.messages.length > 0 
                ? apiState.messages 
                : s.messages
              return {
                ...s,
                messages: updatedMessages,
                updatedAt: Date.now()
              }
            }
            return s
          })
        }
      }),
      
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

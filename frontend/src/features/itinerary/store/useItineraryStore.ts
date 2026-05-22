import { create } from 'zustand'
import type { ClosedLoopState } from '../model/types'

export type InvokeStatus = 'idle' | 'running' | 'success' | 'error'

function commuteModeLabel(mode: 'walking' | 'taxi' | 'driving'): string {
  if (mode === 'walking') return '步行'
  if (mode === 'taxi') return '打车'
  return '自驾'
}

type ItineraryStore = {
  sessionId: string | null
  userInput: string
  invokeStatus: InvokeStatus
  state: ClosedLoopState | null
  errorMessage: string | null
  setUserInput: (v: string) => void
  startSession: (sessionId: string, userInput: string) => void
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

export const useItineraryStore = create<ItineraryStore>((set) => ({
  sessionId: null,
  userInput: '',
  invokeStatus: 'idle',
  state: null,
  errorMessage: null,
  setUserInput: (v) => set({ userInput: v }),
  startSession: (sessionId, userInput) =>
    set({
      sessionId,
      userInput,
      invokeStatus: 'idle',
      state: null,
      errorMessage: null,
    }),
  setInvokeRunning: () => set({ invokeStatus: 'running', errorMessage: null }),
  setInvokeSuccess: (state) =>
    set({ invokeStatus: 'success', state, errorMessage: null }),
  setInvokeError: (message) =>
    set({ invokeStatus: 'error', errorMessage: message }),
  updateCommuteMode: (planId, commuteItemId, mode) =>
    set((prev) => {
      if (!prev.state?.itinerary?.plans) return prev
      const nextState = structuredClone(prev.state)
      const plan = nextState.itinerary?.plans?.find((p) => p.plan_id === planId)
      if (!plan) return prev
      const step = plan.steps.find((s) => s.item.id === commuteItemId)
      if (!step) return prev
      const opts = step.item.commute_options ?? []
      const chosen = opts.find((o) => o.mode === mode) ?? null
      if (!chosen) return prev
      const prevDuration = Number.isFinite(step.duration_minutes) ? step.duration_minutes : 0
      const prevCost = typeof step.item.cost === 'number' && Number.isFinite(step.item.cost) ? step.item.cost : 0
      if (!step.item.commute_recommended_mode) {
        step.item.commute_recommended_mode = step.item.commute_mode ?? null
      }
      step.item.commute_mode = mode
      step.duration_minutes = chosen.time_minutes
      step.item.cost = chosen.cost
      step.note = `已将出行方式改为 ${commuteModeLabel(mode)}`

      const nextDuration = Number.isFinite(step.duration_minutes) ? step.duration_minutes : 0
      const nextCost = typeof step.item.cost === 'number' && Number.isFinite(step.item.cost) ? step.item.cost : 0

      if (typeof plan.total_duration_minutes === 'number' && Number.isFinite(plan.total_duration_minutes)) {
        plan.total_duration_minutes = Math.max(0, plan.total_duration_minutes + (nextDuration - prevDuration))
      }
      if (typeof plan.total_cost === 'number' && Number.isFinite(plan.total_cost)) {
        plan.total_cost = Math.max(0, plan.total_cost + (nextCost - prevCost))
      }
      return { ...prev, state: nextState }
    }),
  reset: () =>
    set({
      sessionId: null,
      userInput: '',
      invokeStatus: 'idle',
      state: null,
      errorMessage: null,
    }),
}))

import { beforeEach, describe, expect, it } from 'vitest'
import { useItineraryStore } from '../useItineraryStore'
import type { MockPaymentCommitResponse } from '../../api/invoke'

const result: MockPaymentCommitResponse = { execution_id: 'command-a', payment_status: 'paid', commit_status: 'success' }

beforeEach(() => {
  localStorage.clear()
  useItineraryStore.setState({ sessions: [], currentSessionId: null })
  const store = useItineraryStore.getState()
  store.startSession('a', '订单 A')
  store.setInvokeSuccess({ user_input: '支付测试', confirmation: { status: 'pending_payment', execution_id: 'command-a' } })
})

describe('payment response ownership and status', () => {
  it('updates the originating command after switching sessions', () => {
    const store = useItineraryStore.getState()
    store.startSession('b', '订单 B')
    store.setInvokeSuccess({ user_input: '支付测试', confirmation: { status: 'pending_payment', execution_id: 'command-b' } })
    store.applyPaymentCommit(result)
    const sessions = useItineraryStore.getState().sessions
    expect(sessions.find(s => s.id === 'a')?.confirmation?.status).toBe('executed')
    expect(sessions.find(s => s.id === 'b')?.confirmation?.status).toBe('pending_payment')
  })

  it('ignores an old command after the session receives a new order', () => {
    const store = useItineraryStore.getState()
    store.setInvokeSuccess({ user_input: '支付测试', confirmation: { status: 'pending_payment', execution_id: 'command-new' } })
    store.applyPaymentCommit(result)
    expect(useItineraryStore.getState().sessions[0].confirmation?.execution_id).toBe('command-new')
    expect(useItineraryStore.getState().sessions[0].confirmation?.status).toBe('pending_payment')
  })

  it('keeps incorrect-password commands available for correction', () => {
    useItineraryStore.getState().applyPaymentCommit({ ...result, payment_status: 'failed', commit_status: 'not_started' })
    expect(useItineraryStore.getState().sessions[0].confirmation?.status).toBe('pending_payment')
  })

  it('does not downgrade a completed order with a late incorrect-password response', () => {
    const store = useItineraryStore.getState()
    store.applyPaymentCommit(result)
    store.applyPaymentCommit({ ...result, payment_status: 'failed', commit_status: 'not_started' })
    expect(useItineraryStore.getState().sessions[0].confirmation?.status).toBe('executed')
  })

  it('preserves partial failure details even if the Mock payment is paid', () => {
    useItineraryStore.getState().applyPaymentCommit({ ...result, commit_status: 'failed',
      items: [{ item_id: 'first', reserved: true }], failures: [{ item_id: 'sold-out' }] })
    const confirmation = useItineraryStore.getState().sessions[0].confirmation
    expect(confirmation?.status).toBe('failed')
    expect(confirmation?.execution_summary?.items).toEqual([{ item_id: 'first', reserved: true }])
    expect(confirmation?.execution_summary?.failures).toEqual([{ item_id: 'sold-out' }])
  })
})

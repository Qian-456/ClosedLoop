import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PlanPanel } from '../PlanPanel'
import { useItineraryStore } from '../../store/useItineraryStore'
import { commitMockPayment } from '../../api/invoke'

vi.mock('../../api/invoke', () => ({ commitMockPayment: vi.fn() }))

function ConnectedPanel() {
  const confirmation = useItineraryStore(s => s.sessions[0]?.confirmation)
  return <PlanPanel confirmation={confirmation} />
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  useItineraryStore.setState({ sessions: [], currentSessionId: null, invokeStatus: 'idle' })
  const store = useItineraryStore.getState()
  store.startSession('payment-test', '支付测试')
  store.setInvokeSuccess({ user_input: '支付测试', confirmation: { status: 'pending_payment', execution_id: 'payment-command' } })
})

function submit() {
  for (let i = 0; i < 6; i++) fireEvent.click(screen.getByRole('button', { name: /^1$/ }))
  fireEvent.click(screen.getByRole('button', { name: '确认支付' }))
}

describe('payment UI response handling', () => {
  it('shows completion only for a successful execution response', async () => {
    vi.mocked(commitMockPayment).mockResolvedValue({ execution_id: 'payment-command', payment_status: 'paid',
      commit_status: 'success', items: [{ item_id: 'booked', reserved: true }] })
    render(<ConnectedPanel />)
    submit()
    expect(await screen.findByText('执行已完成')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '确认支付' })).not.toBeInTheDocument()
  })

  it('renders paid-but-failed execution and retains its failed item', async () => {
    vi.mocked(commitMockPayment).mockResolvedValue({ execution_id: 'payment-command', payment_status: 'paid',
      commit_status: 'failed', message: '活动库存不足', failures: [{ item_id: 'sold-out' }] })
    render(<ConnectedPanel />)
    submit()
    expect(await screen.findByText('执行未完成')).toBeInTheDocument()
    expect(screen.getByText('sold-out')).toBeInTheDocument()
    expect(screen.queryByText('执行已完成')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '确认支付' })).not.toBeInTheDocument()
  })

  it('keeps keypad available for an incorrect password', async () => {
    vi.mocked(commitMockPayment).mockResolvedValue({ execution_id: 'payment-command', payment_status: 'failed',
      commit_status: 'not_started', message: '密码错误' })
    render(<ConnectedPanel />)
    submit()
    await waitFor(() => expect(screen.getByRole('button', { name: '确认支付' })).toBeEnabled())
    expect(useItineraryStore.getState().sessions[0].confirmation?.status).toBe('pending_payment')
  })

  it('shows uncertain execution without offering another full-order payment', async () => {
    vi.mocked(commitMockPayment).mockResolvedValue({ execution_id: 'payment-command', payment_status: 'unknown',
      commit_status: 'unknown', message: '请核对库存' })
    render(<ConnectedPanel />)
    submit()
    expect(await screen.findByText('执行结果待核对')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '确认支付' })).not.toBeInTheDocument()
  })
})

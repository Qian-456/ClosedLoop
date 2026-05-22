import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { executeStart } from '../../features/itinerary/api/executeStart'
import { useItineraryStore } from '../../features/itinerary/store/useItineraryStore'
import ExecutingPage from '../ExecutingPage'
import JourneyReadyPage from '../JourneyReadyPage'

vi.mock('../../features/itinerary/api/executeStart', () => {
  return {
    executeStart: vi.fn(async () => ({ execution_id: 'exe_1' })),
  }
})

class FakeEventSource {
  url: string
  onmessage: ((ev: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }
  close() {
    this.closed = true
  }
  emit(data: unknown) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) })
  }
  static instances: FakeEventSource[] = []
}

describe('ExecutingPage', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    ;(globalThis as any).EventSource = FakeEventSource as any
    vi.mocked(executeStart).mockReset()
    vi.mocked(executeStart).mockResolvedValue({ execution_id: 'exe_1' })

    useItineraryStore.getState().reset()
    useItineraryStore.getState().setInvokeSuccess({
      user_input: 'x',
      constraints: { time_period: '14:00' },
      itinerary: {
        status: 'ok',
        plans: [
          {
            plan_id: 'plan_1',
            title: '方案A',
            steps: [
              {
                order_id: '1',
                duration_minutes: 10,
                note: '',
                item: {
                  id: 'combo_1',
                  name: '套餐',
                  display_name: '海底捞',
                  parent_name: '海底捞',
                  sub_name: '双人套餐',
                  type: 'restaurant',
                  location: 'x',
                  distance_km: 1,
                  cost: 100,
                },
              },
              {
                order_id: '2',
                duration_minutes: 20,
                note: '',
                item: {
                  id: 'package_1',
                  name: '门票',
                  display_name: '未来探索中心',
                  parent_name: '未来探索中心',
                  sub_name: '沉浸式体验票',
                  type: 'activity',
                  location: 'x',
                  distance_km: 1,
                  cost: 50,
                },
              },
              {
                order_id: '3',
                duration_minutes: 10,
                note: '',
                item: {
                  id: 'gift_1',
                  name: '礼物',
                  type: 'gift_shop',
                  location: 'x',
                  distance_km: 1,
                  cost: 99,
                  gift_price: 99,
                  delivery_fee: 0,
                  delivery_distance_km: 1,
                },
              },
              {
                order_id: 'C1',
                duration_minutes: 5,
                note: '',
                item: {
                  id: 'commute_x',
                  name: '通勤',
                  display_name: '海底捞 -> 未来探索中心',
                  sub_name: '推荐方式：打车',
                  type: 'commute',
                  location: 'x',
                  distance_km: 1,
                  cost: 0,
                  commute_from: '海底捞',
                  commute_to: '未来探索中心',
                  commute_mode: 'taxi',
                },
              },
            ],
            selected_item_ids: ['combo_1', 'package_1', 'gift_1'],
            total_duration_minutes: 45,
            total_cost: 249,
            average_score: 10,
          },
        ],
      },
    })
  })

  it('开始执行完成后显示执行完成与底部三按钮', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [
        { path: '/app/executing/:planId', element: <ExecutingPage /> },
        { path: '/app/journey/:planId', element: <JourneyReadyPage /> },
      ],
      { initialEntries: ['/app/executing/plan_1'] },
    )
    render(<RouterProvider router={router} />)

    expect(screen.getByText('开始流程')).toBeInTheDocument()
    expect(screen.getByText('预定出租车：海底捞 → 未来探索中心')).toBeInTheDocument()
    expect(screen.getByText('海底捞')).toBeInTheDocument()
    expect(screen.getByText('未来探索中心')).toBeInTheDocument()
    expect(FakeEventSource.instances.length).toBe(0)
    expect(screen.queryByText('分享行程')).toBeNull()

    await user.click(screen.getByText('开始流程'))

    const es = await waitFor(() => {
      expect(FakeEventSource.instances.length).toBeGreaterThan(0)
      return FakeEventSource.instances[0]
    })

    es.emit({
      type: 'item_update',
      data: {
        item_id: 'package_1',
        item_type: 'activity',
        phase: 'checking',
        message: '正在读取当前活动是否还有票/库存…',
      },
    })

    expect(await screen.findByText('正在读取当前活动是否还有票/库存…')).toBeInTheDocument()

    es.emit({ type: 'done', data: { status: 'ok' } })

    expect((await screen.findAllByText('执行完成')).length).toBeGreaterThan(0)
    expect(await screen.findByText('分享行程')).toBeInTheDocument()
    expect(await screen.findByText('预定提醒')).toBeInTheDocument()
    expect(await screen.findByText('进入流程')).toBeInTheDocument()

    await user.click(await screen.findByText('进入流程'))
    expect(await screen.findByText('让我们准备开启今天的行程吧')).toBeInTheDocument()
    expect(await screen.findByText('开始流程')).toBeInTheDocument()
  })

  it('EventSource 连接中断后可以重新开始流程', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [{ path: '/app/executing/:planId', element: <ExecutingPage /> }],
      { initialEntries: ['/app/executing/plan_1'] },
    )
    render(<RouterProvider router={router} />)

    await user.click(screen.getByText('开始流程'))

    const first = await waitFor(() => {
      expect(FakeEventSource.instances.length).toBe(1)
      return FakeEventSource.instances[0]
    })

    first.onerror?.()

    expect(await screen.findByText('连接中断，请重试')).toBeInTheDocument()

    await user.click(screen.getByText('开始执行'))

    await waitFor(() => {
      expect(vi.mocked(executeStart)).toHaveBeenCalledTimes(2)
      expect(FakeEventSource.instances.length).toBe(2)
    })
  })

  it('开始请求失败后可以重新开始流程', async () => {
    vi.mocked(executeStart)
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce({ execution_id: 'exe_2' })

    const user = userEvent.setup()
    const router = createMemoryRouter(
      [{ path: '/app/executing/:planId', element: <ExecutingPage /> }],
      { initialEntries: ['/app/executing/plan_1'] },
    )
    render(<RouterProvider router={router} />)

    await user.click(screen.getByText('开始流程'))

    expect(await screen.findByText('请求失败：boom')).toBeInTheDocument()

    await user.click(screen.getByText('开始执行'))

    await waitFor(() => {
      expect(vi.mocked(executeStart)).toHaveBeenCalledTimes(2)
      expect(FakeEventSource.instances.length).toBe(1)
      expect(FakeEventSource.instances[0]?.url).toContain('/execute/events/exe_2')
    })
  })
})

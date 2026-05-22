import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import PlanDetailPage from '../PlanDetailPage'
import ExecutingPage from '../ExecutingPage'
import { useItineraryStore } from '../../features/itinerary/store/useItineraryStore'

describe('PlanDetailPage', () => {
  beforeEach(() => {
    useItineraryStore.getState().reset()
    useItineraryStore.getState().setInvokeSuccess({
      user_input: 'x',
      constraints: { time_period: '13:00' },
      confirmation: {
        status: 'ok',
        plans: {
          plan_2: {
            plan_name: '平衡体验版',
            pros_cons: ['✔节奏不赶', '✔有小惊喜', '✘预算略高'],
            ai_reminder: '如果要带小朋友，建议活动结束后留 10 分钟缓冲。',
          },
        },
      },
      itinerary: {
        status: 'ok',
        plans: [
          {
            plan_id: 'plan_2',
            title: '方案B',
            steps: [
              {
                order_id: '1',
                duration_minutes: 60,
                note: 'x',
                item: {
                  id: 'a',
                  name: '亲子互动套票',
                  display_name: '奇趣探索馆',
                  parent_name: '奇趣探索馆',
                  sub_name: '亲子互动套票',
                  type: 'activity',
                  location: 'x',
                  distance_km: 1,
                  cost: 0,
                  intro: '亲子互动型室内游乐区',
                  features: '适合放电，亲子友好',
                },
              },
              {
                order_id: '2',
                duration_minutes: 30,
                note: 'x',
                item: {
                  id: 'b',
                  name: '惊喜礼物站',
                  type: 'gift_shop',
                  location: 'x',
                  distance_km: 1,
                  cost: 23,
                  gift_price: 20,
                  delivery_fee: 3,
                  delivery_distance_km: 1,
                  intro: '随手带走的小礼物',
                  features: '小惊喜不尴尬',
                },
              },
              {
                order_id: '3',
                duration_minutes: 14,
                note: '',
                item: {
                  id: 'c',
                  name: '返回回家',
                  display_name: '奇趣探索馆 -> 家',
                  sub_name: '推荐方式：打车',
                  type: 'commute',
                  location: '',
                  distance_km: 1,
                  cost: 12,
                  commute_from: '奇趣探索馆',
                  commute_to: '家',
                  commute_mode: 'taxi',
                  commute_recommended_mode: 'taxi',
                  commute_options: [],
                },
              },
            ],
            selected_item_ids: [],
            total_duration_minutes: 104,
            total_cost: 35,
            average_score: 11,
          },
        ],
      },
    })
  })

  it('根据 time_period 推算第一步 start_time', () => {
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    expect(screen.getByText('13:00')).toBeInTheDocument()
    expect(screen.getByText('奇趣探索馆')).toBeInTheDocument()
    expect(screen.getByText('亲子互动套票')).toBeInTheDocument()
  })

  it('gift_shop 以独立卡片展示并显示预计完成时间', () => {
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    expect(screen.getByText('预计 14:30 前完成')).toBeInTheDocument()
    expect(screen.queryByText('14:00')).not.toBeInTheDocument()
  })

  it('通勤步骤展示预计到家时间', () => {
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    expect(screen.getByText('奇趣探索馆 -> 家')).toBeInTheDocument()
    expect(screen.getByText('推荐方式：打车')).toBeInTheDocument()
    expect(screen.getByText('预计 14:44 到家')).toBeInTheDocument()
  })

  it('可调整结束到家时间并回推开始时间', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    await user.click(screen.getByLabelText('调整到家时间'))
    expect(await screen.findByText('调整到家时间')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '+15 分钟' }))
    await user.click(screen.getByRole('button', { name: '确认' }))

    expect(await screen.findByText('预计 14:59 到家')).toBeInTheDocument()
    expect(await screen.findByText('13:15')).toBeInTheDocument()
  })

  it('不展示底部三个调整按钮', () => {
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    expect(screen.queryByText('降预算')).not.toBeInTheDocument()
    expect(screen.queryByText('更亲子')).not.toBeInTheDocument()
    expect(screen.queryByText('少走路')).not.toBeInTheDocument()
  })

  it('点击开始时间可调整初始时间并确认生效', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    await user.click(screen.getByLabelText('调整初始时间'))

    expect(await screen.findByText('调整初始时间')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '+15 分钟' }))
    await user.click(screen.getByRole('button', { name: '确认' }))

    expect(await screen.findByText('13:15')).toBeInTheDocument()
  })

  it('可恢复为原来的时间', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    await user.click(screen.getByLabelText('调整初始时间'))
    await user.click(screen.getByRole('button', { name: '+15 分钟' }))
    await user.click(screen.getByRole('button', { name: '确认' }))
    expect(await screen.findByText('13:15')).toBeInTheDocument()

    await user.click(screen.getByLabelText('调整初始时间'))
    await user.click(screen.getByRole('button', { name: '恢复' }))

    expect(await screen.findByText('调整初始时间')).toBeInTheDocument()
    expect(await screen.findByText('13:00')).toBeInTheDocument()
  })

  it('点击步骤可打开详情弹层', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    await user.click(screen.getAllByText('奇趣探索馆')[0])
    expect(await screen.findByText('地址 / 位置')).toBeInTheDocument()
    expect((await screen.findAllByText('亲子互动套票')).length).toBeGreaterThan(0)
    expect(await screen.findByText('亲子互动型室内游乐区')).toBeInTheDocument()
    expect(await screen.findByText('适合放电，亲子友好')).toBeInTheDocument()
  })

  it('点击礼物可看到配送费拆分与礼物详情', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    await user.click(screen.getAllByText('惊喜礼物站')[0])

    expect(await screen.findByText('配送信息')).toBeInTheDocument()
    expect(await screen.findByText('礼物价格')).toBeInTheDocument()
    expect(await screen.findByText('配送费')).toBeInTheDocument()
    expect(await screen.findByText('配送距离')).toBeInTheDocument()
    expect(await screen.findByText('随手带走的小礼物')).toBeInTheDocument()
    expect(await screen.findByText('小惊喜不尴尬')).toBeInTheDocument()
  })

  it('展示 copywriting 的优缺点与提醒', () => {
    const router = createMemoryRouter(
      [{ path: '/app/plans/:planId', element: <PlanDetailPage /> }],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    expect(screen.getByText('为什么推荐这套')).toBeInTheDocument()
    expect(screen.getByText('✔节奏不赶')).toBeInTheDocument()
    expect(screen.getByText('如果要带小朋友，建议活动结束后留 10 分钟缓冲。')).toBeInTheDocument()
  })

  it('点击选择方案后进入执行页', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [
        { path: '/app/plans/:planId', element: <PlanDetailPage /> },
        { path: '/app/executing/:planId', element: <ExecutingPage /> },
      ],
      { initialEntries: ['/app/plans/plan_2'] },
    )

    render(<RouterProvider router={router} />)

    await user.click(screen.getByRole('button', { name: '选择这套方案' }))

    expect(await screen.findByText('执行中')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/app/executing/plan_2')
  })
})

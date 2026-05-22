import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import PlansPage from '../PlansPage'
import { useItineraryStore } from '../../features/itinerary/store/useItineraryStore'

describe('PlansPage', () => {
  beforeEach(() => {
    useItineraryStore.getState().reset()
    useItineraryStore.getState().setInvokeSuccess({
      user_input: 'x',
      constraints: { time_period: '13:00' },
      confirmation: {
        status: 'ok',
        plans: {
          plan_1: {
            plan_name: '省钱轻松版',
            pros_cons: ['✔预算更稳', '✔节奏更松', '✘丰富度一般'],
            ai_reminder: '适合想少花点、别太赶的情况。',
          },
          plan_2: {
            plan_name: '平衡体验版',
            pros_cons: ['✔体验更均衡', '✔吃玩都有', '✘花费略高'],
            ai_reminder: '想要体验感又不想太累，选这套更稳。',
          },
          plan_3: {
            plan_name: '高配尽兴版',
            pros_cons: ['✔内容更丰富', '✔更有仪式感', '✘预算压力大'],
            ai_reminder: '更适合把今天当作“认真玩”的一天。',
          },
        },
      },
      itinerary: {
        status: 'ok',
        plans: [
          {
            plan_id: 'plan_1',
            title: '方案A',
            steps: [],
            selected_item_ids: [],
            total_duration_minutes: 60,
            total_cost: 100,
            average_score: 10,
            experience_score: 70,
          },
          {
            plan_id: 'plan_2',
            title: '方案B',
            steps: [],
            selected_item_ids: [],
            total_duration_minutes: 70,
            total_cost: 120,
            average_score: 11,
            experience_score: 88,
          },
          {
            plan_id: 'plan_3',
            title: '方案C',
            steps: [],
            selected_item_ids: [],
            total_duration_minutes: 80,
            total_cost: 150,
            average_score: 9,
            experience_score: 92,
          },
        ],
      },
    })
  })

  it('能渲染 3 套方案卡片', () => {
    const router = createMemoryRouter([{ path: '/app/plans', element: <PlansPage /> }], {
      initialEntries: ['/app/plans'],
    })

    render(<RouterProvider router={router} />)

    expect(screen.getByText('省钱轻松版')).toBeInTheDocument()
    expect(screen.getByText('平衡体验版')).toBeInTheDocument()
    expect(screen.getByText('高配尽兴版')).toBeInTheDocument()
    expect(screen.getByText('✔预算更稳')).toBeInTheDocument()
  })

  it('展示底部可交互抽屉', () => {
    const router = createMemoryRouter([{ path: '/app/plans', element: <PlansPage /> }], {
      initialEntries: ['/app/plans'],
    })

    render(<RouterProvider router={router} />)

    expect(screen.getByText('三个都不满意？')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '机器人' })).toBeInTheDocument()
    expect(screen.getByText(/选择一个最合适的方案以便整体安排/)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText('或者直接告诉我你的想法…')).not.toBeInTheDocument()
  })

  it('可提交调整并跳转到生成页', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter(
      [
        { path: '/app/plans', element: <PlansPage /> },
        { path: '/app/generating', element: <div>generating</div> },
      ],
      { initialEntries: ['/app/plans'] },
    )

    render(<RouterProvider router={router} />)

    await user.click(screen.getByLabelText('打开输入框'))
    await user.type(screen.getByPlaceholderText('或者直接告诉我你的想法…'), '少走路一点')
    await user.click(screen.getByRole('button', { name: '发送' }))
    expect(await screen.findByText('generating')).toBeInTheDocument()
  })

  it('永远推荐 plan_2 并展示推荐指数', () => {
    const router = createMemoryRouter([{ path: '/app/plans', element: <PlansPage /> }], {
      initialEntries: ['/app/plans'],
    })

    render(<RouterProvider router={router} />)

    expect(screen.getAllByText(/推荐指数/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/推荐指数 88/).length).toBeGreaterThan(0)
  })

  it('备选方案也展示推荐指数', () => {
    const router = createMemoryRouter([{ path: '/app/plans', element: <PlansPage /> }], {
      initialEntries: ['/app/plans'],
    })

    render(<RouterProvider router={router} />)

    expect(screen.getAllByText(/推荐指数/).length).toBeGreaterThanOrEqual(3)
  })
})

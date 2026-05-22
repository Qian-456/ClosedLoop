import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import GeneratingPage from '../GeneratingPage'
import { useItineraryStore } from '../../features/itinerary/store/useItineraryStore'

vi.mock('../../shared/lib/sleep', () => {
  return {
    sleep: vi.fn(async () => {}),
  }
})

vi.mock('../../features/itinerary/api/invoke', () => {
  return {
    invoke: vi.fn(async () => ({
      status: 'success',
      state: {
        user_input: 'x',
        constraints: { time_period: '13:00' },
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
            },
          ],
        },
      },
    })),
  }
})

describe('GeneratingPage', () => {
  beforeEach(() => {
    useItineraryStore.getState().reset()
    useItineraryStore.getState().startSession('s1', 'test input')
  })

  it('请求成功后跳转到 plans', async () => {
    const router = createMemoryRouter(
      [
        { path: '/app/generating', element: <GeneratingPage /> },
        { path: '/app/plans', element: <div>plans</div> },
      ],
      { initialEntries: ['/app/generating'] },
    )

    render(<RouterProvider router={router} />)

    expect(await screen.findByText('plans')).toBeInTheDocument()
  })
})

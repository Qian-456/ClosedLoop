import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { useItineraryStore } from '../../features/itinerary/store/useItineraryStore'
import JourneyReadyPage from '../JourneyReadyPage'

describe('JourneyReadyPage', () => {
  beforeEach(() => {
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
                duration_minutes: 60,
                note: '',
                item: {
                  id: 'combo_1',
                  name: '双人欢聚套餐',
                  display_name: '海底捞',
                  parent_name: '海底捞',
                  sub_name: '双人欢聚套餐',
                  type: 'restaurant',
                  location: 'x',
                  distance_km: 1,
                  cost: 100,
                },
              },
              {
                order_id: '2',
                duration_minutes: 15,
                note: '',
                item: {
                  id: 'commute_1',
                  name: '前往 未来探索中心',
                  display_name: '海底捞 -> 未来探索中心',
                  sub_name: '推荐方式：打车',
                  type: 'commute',
                  location: '途中',
                  distance_km: 1.5,
                  cost: 12,
                  commute_from: '海底捞',
                  commute_to: '未来探索中心',
                  commute_mode: 'taxi',
                },
              },
              {
                order_id: '3',
                duration_minutes: 90,
                note: '',
                item: {
                  id: 'package_1',
                  name: '沉浸式体验票',
                  display_name: '未来探索中心',
                  parent_name: '未来探索中心',
                  sub_name: '沉浸式体验票',
                  type: 'activity',
                  location: 'y',
                  distance_km: 2,
                  cost: 80,
                },
              },
            ],
            selected_item_ids: ['combo_1', 'package_1'],
            total_duration_minutes: 165,
            total_cost: 192,
            average_score: 10,
          },
        ],
      },
    })
  })

  it('展示地点名作为大字，套餐名作为小字，通勤显示地点到地点', () => {
    const router = createMemoryRouter([{ path: '/app/journey/:planId', element: <JourneyReadyPage /> }], {
      initialEntries: ['/app/journey/plan_1'],
    })

    render(<RouterProvider router={router} />)

    expect(screen.getByText('海底捞')).toBeInTheDocument()
    expect(screen.getByText('双人欢聚套餐')).toBeInTheDocument()
    expect(screen.getByText('海底捞 -> 未来探索中心')).toBeInTheDocument()
    expect(screen.getByText('推荐方式：打车')).toBeInTheDocument()
    expect(screen.getByText('未来探索中心')).toBeInTheDocument()
    expect(screen.getByText('沉浸式体验票')).toBeInTheDocument()
  })
})

import { beforeEach, describe, expect, it } from 'vitest'
import { useItineraryStore } from '../useItineraryStore'

describe('useItineraryStore.updateCommuteMode', () => {
  beforeEach(() => {
    useItineraryStore.getState().reset()
    useItineraryStore.getState().setInvokeSuccess({
      user_input: 'x',
      constraints: { time_period: '13:00' },
      itinerary: {
        status: 'ok',
        plans: [
          {
            plan_id: 'plan_2',
            title: '方案B',
            selected_item_ids: [],
            average_score: 10,
            total_duration_minutes: 60,
            total_cost: 100,
            steps: [
              {
                order_id: 'C1',
                duration_minutes: 10,
                note: '',
                item: {
                  id: 'commute_1',
                  name: '前往 A',
                  type: 'commute',
                  location: '途中',
                  distance_km: 3,
                  cost: 0,
                  commute_mode: 'walking',
                  commute_options: [
                    { mode: 'walking', time_minutes: 10, cost: 0 },
                    { mode: 'taxi', time_minutes: 5, cost: 10 },
                    { mode: 'driving', time_minutes: 7, cost: 0 },
                  ],
                },
              },
              {
                order_id: 'A1',
                duration_minutes: 50,
                note: '',
                item: {
                  id: 'act_1',
                  name: '活动',
                  type: 'activity',
                  location: 'x',
                  distance_km: 0,
                  cost: 100,
                },
              },
            ],
          },
        ],
      },
    })
  })

  it('切换通勤方式会同步更新总时长与总花费', () => {
    useItineraryStore.getState().updateCommuteMode('plan_2', 'commute_1', 'taxi')
    const state = useItineraryStore.getState().state
    const plan = state?.itinerary?.plans?.[0]
    expect(plan?.total_duration_minutes).toBe(55)
    expect(plan?.total_cost).toBe(110)
  })
})

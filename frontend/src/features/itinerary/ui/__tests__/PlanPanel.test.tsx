import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PlanPanel } from '../PlanPanel'

describe('PlanPanel', () => {
  it('有结果时默认折叠，只展示摘要', () => {
    render(
      <PlanPanel
        itinerary={{
          status: 'ok',
          plans: [
            {
              plan_id: 'plan_1',
              title: '午餐 + 玩 + 惊喜行程方案 A',
              steps: [
                {
                  order_id: '1',
                  duration_minutes: 60,
                  note: '',
                  item: {
                    id: 'item_1',
                    name: '商场家庭餐厅',
                    type: 'restaurant',
                    location: 'CBD',
                    distance_km: 1.2,
                  },
                },
              ],
              selected_item_ids: [],
              total_duration_minutes: 340,
              total_cost: 436.99,
              average_score: 96.2,
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('推荐方案')).toBeInTheDocument()
    expect(screen.getByText('已生成 1 套可执行方案')).toBeInTheDocument()
    expect(screen.queryByText('午餐 + 玩 + 惊喜行程方案 A')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '展开方案面板' })).toBeInTheDocument()
  })

  it('展开后显示完整方案内容，并支持再次收起', () => {
    render(
      <PlanPanel
        itinerary={{
          status: 'ok',
          plans: [
            {
              plan_id: 'plan_1',
              title: '午餐 + 玩 + 惊喜行程方案 A',
              steps: [
                {
                  order_id: '1',
                  duration_minutes: 60,
                  note: '',
                  item: {
                    id: 'item_1',
                    name: '商场家庭餐厅',
                    type: 'restaurant',
                    location: 'CBD',
                    distance_km: 1.2,
                  },
                },
              ],
              selected_item_ids: [],
              total_duration_minutes: 340,
              total_cost: 436.99,
              average_score: 96.2,
            },
          ],
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '展开方案面板' }))

    expect(screen.getByText('午餐 + 玩 + 惊喜行程方案 A')).toBeInTheDocument()
    expect(screen.getByText('1. 商场家庭餐厅')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '收起方案面板' }))

    expect(screen.queryByText('午餐 + 玩 + 惊喜行程方案 A')).not.toBeInTheDocument()
  })
})

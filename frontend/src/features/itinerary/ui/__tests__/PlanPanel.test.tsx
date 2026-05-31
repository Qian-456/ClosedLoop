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

  it('当需要补齐时展示候选提示', () => {
    render(
      <PlanPanel
        confirmation={{
          status: 'needs_fixup',
          fixup: {
            backup_candidates: [
              { id: 'combo_2', name: '备选餐厅A', violation_reason: '超出预算或时间' },
              { id: 'combo_3', name: '备选餐厅B', violation_reason: '距离略远' },
            ],
          },
        }}
      />,
    )

    expect(screen.getByText('需要你确认')).toBeInTheDocument()
    expect(screen.getByText('候选1：备选餐厅A')).toBeInTheDocument()
    expect(screen.getByText('候选2：备选餐厅B')).toBeInTheDocument()
  })

  it('执行完成后在面板内展示执行结果', () => {
    render(
      <PlanPanel
        itinerary={{
          status: 'ok',
          plans: [
            {
              plan_id: 'plan_1',
              title: '午餐 + 玩 + 惊喜行程方案 A',
              steps: [],
              selected_item_ids: [],
              total_duration_minutes: 340,
              total_cost: 436.99,
              average_score: 96.2,
            },
          ],
        }}
        confirmation={{
          status: 'executed',
          execution_summary: {
            execution_id: 'exe_1',
            replacements: [
              {
                original_id: 'combo_1',
                original_name: '主选餐厅',
                new_item_id: 'combo_2',
                new_item_name: '备选餐厅',
                item_type: 'restaurant',
              },
            ],
            failures: [
              {
                item_id: 'package_1',
                item_name: '活动门票',
                item_type: 'activity',
              },
            ],
          },
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '展开方案面板' }))

    expect(screen.getByText('执行结果')).toBeInTheDocument()
    expect(screen.getByText('已替换 1 项')).toBeInTheDocument()
    expect(screen.getByText('主选餐厅 → 备选餐厅')).toBeInTheDocument()
    expect(screen.getByText('失败 1 项')).toBeInTheDocument()
    expect(screen.getByText('活动门票')).toBeInTheDocument()
  })

  
})

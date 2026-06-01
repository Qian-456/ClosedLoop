import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PlanPanel } from '../PlanPanel'

const samplePlan = {
  plan_id: 'plan_1',
  title: '亲子平衡乐游',
  steps: [
    {
      order_id: '1',
      duration_minutes: 69,
      note: '2大1小家庭套餐',
      start_time: '16:18',
      end_time: '17:27',
      item: {
        id: 'item_1',
        name: '商场家庭餐厅',
        type: 'restaurant' as const,
        location: 'CBD核心商圈',
        distance_km: 1.2,
        cost: 92,
      },
    },
    {
      order_id: '2',
      duration_minutes: 10,
      note: '',
      start_time: '17:27',
      end_time: '17:37',
      item: {
        id: 'commute_1',
        name: '通勤',
        type: 'commute' as const,
        location: 'CBD核心商圈',
        distance_km: 1,
        cost: 10,
        commute_from: '商场家庭餐厅',
        commute_to: '木偶剧小剧场',
        commute_mode: 'taxi' as const,
      },
    },
    {
      order_id: '3',
      duration_minutes: 60,
      note: '2大1小亲子标准体验',
      start_time: '17:37',
      item: {
        id: 'item_2',
        name: '木偶剧小剧场',
        type: 'activity' as const,
        location: 'CBD核心商圈',
        distance_km: 1.8,
        cost: 140,
      },
    },
    {
      order_id: '4',
      duration_minutes: 12,
      note: '亲子版桌游，规则简单易上手',
      item: {
        id: 'item_3',
        name: '益智拼图玩具',
        type: 'gift_shop' as const,
        location: '老城文化街区',
        distance_km: 2.2,
        gift_price: 138,
      },
    },
  ],
  selected_item_ids: ['item_1', 'item_2', 'item_3'],
  total_duration_minutes: 360,
  total_cost: 513,
  average_score: 96.2,
  experience_score: 100,
}

describe('PlanPanel', () => {
  it('有结果时直接展示方案卡片摘要', () => {
    render(
      <PlanPanel
        itinerary={{
          status: 'ok',
          plans: [samplePlan],
        }}
        confirmation={{
          status: 'ok',
          plans: {
            plan_1: {
              plan_name: '亲子平衡乐游',
              pros_cons: ['2个活动搭配，孩子玩得尽兴不累', '总时长6小时，节奏刚好不赶'],
              ai_reminder: '',
            },
          },
        }}
      />,
    )

    expect(screen.getByText('推荐方案')).toBeInTheDocument()
    expect(screen.getByText('已生成 1 套可执行方案')).toBeInTheDocument()
    expect(screen.getByText('亲子平衡乐游')).toBeInTheDocument()
    expect(screen.getByText('推荐指数 100')).toBeInTheDocument()
    expect(screen.getAllByText('¥513').length).toBeGreaterThan(0)
    expect(screen.getByText('2个活动搭配，孩子玩得尽兴不累')).toBeInTheDocument()
    expect(screen.getByText('总时长')).toBeInTheDocument()
    expect(screen.getByText('6h')).toBeInTheDocument()
    expect(screen.queryByText('推荐方式：打车 · 预计 17:37 到达')).not.toBeInTheDocument()
  })

  it('点击 plan 后原地展开完整 timeline 和推荐理由', () => {
    render(
      <PlanPanel
        itinerary={{
          status: 'ok',
          plans: [samplePlan],
        }}
        confirmation={{
          status: 'ok',
          plans: {
            plan_1: {
              plan_name: '亲子平衡乐游',
              pros_cons: ['2个活动搭配，孩子玩得尽兴不累', '总时长6小时，节奏刚好不赶', '礼物安排在后段'],
              ai_reminder: '',
            },
          },
        }}
      />,
    )

    fireEvent.click(screen.getByText('亲子平衡乐游'))

    expect(screen.getByText('为什么推荐这套')).toBeInTheDocument()
    expect(screen.getByText('16:18')).toBeInTheDocument()
    expect(screen.getByText('17:27')).toBeInTheDocument()
    expect(screen.getByText('推荐方式：打车 · 预计 17:37 到达')).toBeInTheDocument()
    expect(screen.getByText('礼物安排在后段')).toBeInTheDocument()
  })

  it('无方案时展示空态', () => {
    render(
      <PlanPanel
        itinerary={{
          status: 'insufficient_candidates',
          plans: [],
        }}
      />,
    )

    expect(screen.getByText('当前条件下暂时没有生成出合适方案，可以继续调整需求后重试。')).toBeInTheDocument()
  })

  it('需要补齐时展示候选提示', () => {
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
    expect(screen.getByText('候选 1：备选餐厅A')).toBeInTheDocument()
    expect(screen.getByText('候选 2：备选餐厅B')).toBeInTheDocument()
  })

  it('执行完成后在面板内展示执行结果', () => {
    render(
      <PlanPanel
        itinerary={{
          status: 'ok',
          plans: [samplePlan],
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

    expect(screen.getByText('执行结果')).toBeInTheDocument()
    expect(screen.getByText('已替换 1 项')).toBeInTheDocument()
    expect(screen.getByText(/主选餐厅/)).toHaveTextContent('主选餐厅 -> 备选餐厅')
    expect(screen.getByText('失败 1 项')).toBeInTheDocument()
    expect(screen.getByText('活动门票')).toBeInTheDocument()
  })
})

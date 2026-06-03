import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PlanPanel } from '../PlanPanel'

const samplePlan = {
  plan_id: 'plan_1',
  title: '午餐 + 玩 + 惊喜行程方案 A',
  steps: [
    {
      order_id: 'C1',
      duration_minutes: 16,
      note: '',
      start_time: '13:00',
      end_time: '13:16',
      item: {
        id: 'commute_1',
        name: '通勤',
        type: 'commute' as const,
        location: '途中',
        distance_km: 1,
        cost: 0,
        price_breakdown: { commute_fee: 0, total: 0 },
        duration_breakdown: { base_minutes: 16, buffer_minutes: 5, total_minutes: 16 },
        commute_from: '家',
        commute_to: '莲香茶餐厅',
        commute_mode: 'walking' as const,
      },
    },
    {
      order_id: '1',
      duration_minutes: 123,
      note: '2大1小家庭套餐',
      start_time: '13:21',
      end_time: '15:24',
      item: {
        id: 'combo_1',
        name: '莲香茶餐厅家庭套餐',
        display_name: '莲香茶餐厅（老城文化街区）',
        sub_name: '2大1小家庭套餐',
        type: 'restaurant' as const,
        location: '老城文化街区',
        distance_km: 1.2,
        cost: 86,
        price_breakdown: { base_price: 86, total: 86 },
        duration_breakdown: { base_minutes: 58, wait_minutes: 65, buffer_minutes: 5, total_minutes: 123 },
        expected_wait_minutes: 65,
        queue_required: true,
        requires_booking: true,
        booking_target_type: 'restaurant' as const,
        booking_target_id: 'restaurant_1',
        intro: '港式茶餐厅，菜品丰富，适合亲子家庭分享用餐。',
        features: '老城文化街区人气老字号，口碑评分高，环境舒适，适合家庭就餐。',
      },
    },
    {
      order_id: '2',
      duration_minutes: 150,
      note: '亲子友好-室内',
      start_time: '15:39',
      end_time: '18:09',
      item: {
        id: 'package_1',
        name: '室内儿童乐园',
        display_name: '室内儿童乐园',
        sub_name: '亲子友好-室内',
        type: 'activity' as const,
        location: 'CBD核心商圈',
        distance_km: 1.8,
        cost: 140,
        price_breakdown: { base_price: 140, total: 140 },
        duration_breakdown: { base_minutes: 150, buffer_minutes: 5, total_minutes: 150 },
        queue_required: false,
        requires_booking: true,
        booking_target_type: 'package' as const,
        booking_target_id: 'package_1',
        intro: '小朋友可以释放体力，家长也能在室内休息。',
        features: '室内亲子体验，动线清晰。',
      },
    },
    {
      order_id: '3',
      duration_minutes: 12,
      note: '惊喜礼物',
      start_time: '18:09',
      end_time: '18:21',
      item: {
        id: 'gift_1',
        name: '亲子桌游惊喜礼物',
        display_name: '惊喜礼物',
        sub_name: '亲子桌游',
        type: 'gift_shop' as const,
        location: '老城文化街区',
        distance_km: 2.2,
        cost: 85,
        gift_price: 73,
        delivery_fee: 12,
        price_breakdown: { gift_price: 73, delivery_fee: 12, total: 85 },
        duration_breakdown: { base_minutes: 12, total_minutes: 12 },
        intro: '适合带回家继续玩的亲子桌游。',
        features: '惊喜感强，规则简单。',
      },
    },
  ],
  selected_item_ids: ['combo_1', 'package_1', 'gift_1'],
  total_duration_minutes: 362,
  total_cost: 311,
  average_score: 86.7,
  experience_score: 87,
}

const sampleConfirmation = {
  status: 'ok',
  plans: {
    plan_1: {
      plan_name: '午餐 + 玩 + 惊喜行程方案 A',
      pros_cons: ['步行可达老城文化街区，整体路线轻松', '餐厅和活动适合亲子家庭'],
      ai_reminder: '',
    },
  },
}

describe('PlanPanel', () => {
  it('有 plans 时默认只显示一个可展开把手', () => {
    render(<PlanPanel itinerary={{ status: 'ok', plans: [samplePlan] }} confirmation={sampleConfirmation} />)

    expect(screen.getByLabelText('展开推荐方案')).toBeInTheDocument()
    expect(screen.queryByText('推荐方案')).not.toBeInTheDocument()
    expect(screen.queryByText('午餐 + 玩 + 惊喜行程方案 A')).not.toBeInTheDocument()
  })

  it('点击把手后显示方案摘要卡列表，点击摘要卡进入行程详情', () => {
    render(<PlanPanel itinerary={{ status: 'ok', plans: [samplePlan] }} confirmation={sampleConfirmation} />)

    fireEvent.click(screen.getByLabelText('展开推荐方案'))
    expect(screen.getByText('推荐方案')).toBeInTheDocument()
    expect(screen.getByText('午餐 + 玩 + 惊喜行程方案 A')).toBeInTheDocument()
    expect(screen.getByText('推荐指数 87')).toBeInTheDocument()
    expect(screen.getByText('¥311')).toBeInTheDocument()
    expect(screen.queryByText(/平均等位/)).not.toBeInTheDocument()
    expect(screen.queryByText('莲香茶餐厅（老城文化街区）')).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('午餐 + 玩 + 惊喜行程方案 A'))
    expect(screen.getByText('返回方案列表')).toBeInTheDocument()
    expect(screen.getByText('莲香茶餐厅（老城文化街区）')).toBeInTheDocument()
    expect(screen.getByText('平均等位 65 分钟')).toBeInTheDocument()
    expect(screen.getByText('总时长 123分钟（含等位65分钟）')).toBeInTheDocument()
  })

  it('展开后可以从把手一键收回到只剩展开条', () => {
    render(<PlanPanel itinerary={{ status: 'ok', plans: [samplePlan] }} confirmation={sampleConfirmation} />)

    fireEvent.click(screen.getByLabelText('展开推荐方案'))
    fireEvent.click(screen.getByText('午餐 + 玩 + 惊喜行程方案 A'))
    fireEvent.click(screen.getByLabelText('收起推荐方案'))

    expect(screen.getByLabelText('展开推荐方案')).toBeInTheDocument()
    expect(screen.queryByText('推荐方案')).not.toBeInTheDocument()
    expect(screen.queryByText('午餐 + 玩 + 惊喜行程方案 A')).not.toBeInTheDocument()
  })

  it('步骤详情层的把手也能一键收回到只剩展开条', () => {
    render(<PlanPanel itinerary={{ status: 'ok', plans: [samplePlan] }} confirmation={sampleConfirmation} />)

    fireEvent.click(screen.getByLabelText('展开推荐方案'))
    fireEvent.click(screen.getByText('午餐 + 玩 + 惊喜行程方案 A'))
    const detailButtons = screen.getAllByRole('button').filter((button) => button.textContent?.includes('详') || button.textContent?.includes('璇'))
    fireEvent.click(detailButtons[0])

    expect(screen.getByText('老城文化街区人气老字号，口碑评分高，环境舒适，适合家庭就餐。')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('收起全部推荐方案'))

    expect(screen.getByLabelText('展开推荐方案')).toBeInTheDocument()
    expect(screen.queryByText('老城文化街区人气老字号，口碑评分高，环境舒适，适合家庭就餐。')).not.toBeInTheDocument()
  })

  it('无方案、needs_fixup、执行结果仍正常展示', () => {
    const { rerender } = render(<PlanPanel itinerary={{ status: 'insufficient_candidates', plans: [] }} />)
    expect(screen.getByText('当前条件下暂时没有生成出合适方案，可以继续调整需求后重试。')).toBeInTheDocument()

    rerender(
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

    rerender(
      <PlanPanel
        itinerary={{ status: 'ok', plans: [samplePlan] }}
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
    fireEvent.click(screen.getByLabelText('展开推荐方案'))
    expect(screen.getByText('执行结果')).toBeInTheDocument()
    expect(screen.getByText('已替换 1 项')).toBeInTheDocument()
    expect(screen.getByText('失败 1 项')).toBeInTheDocument()
  })
})

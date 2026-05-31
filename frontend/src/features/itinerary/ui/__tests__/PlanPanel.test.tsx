import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PlanPanel } from '../PlanPanel'

vi.mock('../../api/invoke', () => ({
  invokeStreamResume: vi.fn(() => new Promise(() => {})),
}))

const applyInvokeStreamEvent = vi.fn()
const setInvokeRunning = vi.fn()
const setInvokeError = vi.fn()

vi.mock('../../store/useItineraryStore', () => ({
  useItineraryStore: (selector: any) =>
    selector({
      currentSessionId: 'thread_test_1',
      applyInvokeStreamEvent,
      setInvokeRunning,
      setInvokeError,
    }),
}))

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

  it('当需要人工确认时展示同意/拒绝按钮', () => {
    render(
      <PlanPanel
        confirmation={{
          status: 'needs_review',
          interrupt: {
            action_requests: [
              {
                name: 'execute_itinerary_replacement',
                arguments: { execution_id: 'exe_1', item_id: 'combo_1', backup_id: 'combo_2' },
                description: '主选无座，是否同意替换？',
              },
            ],
            review_configs: [
              { action_name: 'execute_itinerary_replacement', allowed_decisions: ['approve', 'reject'] },
            ],
          },
        }}
      />,
    )

    expect(screen.getByText('需要你确认')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '拒绝替换' })).toBeInTheDocument()
  })

  it('点击同意后进入提交中状态', () => {
    render(
      <PlanPanel
        confirmation={{
          status: 'needs_review',
          interrupt: {
            action_requests: [
              {
                name: 'execute_itinerary_replacement',
                arguments: { execution_id: 'exe_1', item_id: 'combo_1', backup_id: 'combo_2' },
                description: '主选无座，是否同意替换？',
              },
            ],
            review_configs: [
              { action_name: 'execute_itinerary_replacement', allowed_decisions: ['approve', 'reject'] },
            ],
          },
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '同意替换' }))
    expect(screen.getByText('已确认')).toBeInTheDocument()
    expect(screen.getByText('继续执行中…')).toBeInTheDocument()
    expect(screen.queryByText('需要你确认')).not.toBeInTheDocument()
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

  it('确认请求失败时提示系统将重试', async () => {
    const { invokeStreamResume } = await import('../../api/invoke')
    ;(invokeStreamResume as any).mockRejectedValueOnce(new Error('boom'))

    render(
      <PlanPanel
        confirmation={{
          status: 'needs_review',
          interrupt: {
            action_requests: [
              {
                name: 'execute_itinerary_replacement',
                arguments: { execution_id: 'exe_1', item_id: 'combo_1', backup_id: 'combo_2' },
                description: '主选无座，是否同意替换？',
              },
            ],
            review_configs: [
              { action_name: 'execute_itinerary_replacement', allowed_decisions: ['approve', 'reject'] },
            ],
          },
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '同意替换' }))

    await waitFor(() => {
      expect(setInvokeError).toHaveBeenCalledWith('系统故障会进行重试')
    })
  })
})

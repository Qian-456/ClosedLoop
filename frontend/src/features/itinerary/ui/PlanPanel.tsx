import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

import type { Confirmation, ItineraryPlan } from '../model/types'
import { invokeStreamResume } from '../api/invoke'
import { useItineraryStore } from '../store/useItineraryStore'
import PrimaryButton from '../../../shared/ui/PrimaryButton'

type Props = {
  itinerary?: ItineraryPlan | null
  confirmation?: Confirmation | null
  errorMessage?: string | null
}

/**
 * Renders the final plan result panel after the stream finishes.
 */
export function PlanPanel({ itinerary, confirmation, errorMessage }: Props) {
  const plans = Array.isArray(itinerary?.plans) ? itinerary.plans : []
  const hasPlans = plans.length > 0
  const [expanded, setExpanded] = useState(false)
  const [decisionLoading, setDecisionLoading] = useState(false)
  const [dismissedDecisionKey, setDismissedDecisionKey] = useState<string | null>(null)

  const currentSessionId = useItineraryStore((s) => s.currentSessionId)
  const applyInvokeStreamEvent = useItineraryStore((s) => s.applyInvokeStreamEvent)
  const setInvokeRunning = useItineraryStore((s) => s.setInvokeRunning)
  const setInvokeError = useItineraryStore((s) => s.setInvokeError)
  const summaryText = useMemo(() => {
    if (hasPlans) {
      return `已生成 ${plans.length} 套可执行方案`
    }
    if (confirmation) {
      return `当前确认状态：${confirmation.status}`
    }
    if (errorMessage) {
      return errorMessage
    }
    return '方案生成完成后会展示在这里。'
  }, [confirmation, errorMessage, hasPlans, plans.length])

  const interruptPayload = (confirmation?.interrupt as any) ?? null
  const actionRequests =
    interruptPayload?.action_requests ??
    interruptPayload?.actionRequests ??
    interruptPayload?.action_requests ??
    null

  const firstAction = Array.isArray(actionRequests) && actionRequests.length > 0 ? actionRequests[0] : null
  const firstDescription = firstAction?.description ?? firstAction?.descriptionPrefix ?? null

  const args = (firstAction?.arguments as any) ?? null
  const itemId = typeof args?.item_id === 'string' ? args.item_id : null
  const executionId = typeof args?.execution_id === 'string' ? args.execution_id : null
  const backupId = typeof args?.backup_id === 'string' ? args.backup_id : null
  const currentDecisionKey =
    executionId && itemId && backupId ? `${executionId}:${itemId}:${backupId}` : null

  const executionSummary =
    (confirmation as any)?.execution_summary ?? (confirmation as any)?.executionSummary ?? null
  const replacements = Array.isArray(executionSummary?.replacements) ? executionSummary.replacements : []
  const failures = Array.isArray(executionSummary?.failures) ? executionSummary.failures : []

  const handleDecision = async (type: 'approve' | 'reject') => {
    if (!currentSessionId || decisionLoading || !firstAction) {
      return
    }
    
    setDecisionLoading(true)
    if (currentDecisionKey) {
      setDismissedDecisionKey(currentDecisionKey)
    }
    setInvokeRunning()
    try {
      await invokeStreamResume(
        currentSessionId,
        {
          decisions: [
            {
              type,
              item_id: itemId,
              execution_id: executionId,
              backup_id: backupId,
            },
          ],
        },
        {
          onEvent(event) {
            applyInvokeStreamEvent(event)
          },
        },
      )
    } catch (error) {
      console.error(error)
      setInvokeError('系统故障会进行重试')
      setDismissedDecisionKey(null)
    } finally {
      setDecisionLoading(false)
    }
  }

  useEffect(() => {
    if (confirmation?.status !== 'needs_review') {
      setDismissedDecisionKey(null)
      return
    }
    if (dismissedDecisionKey && currentDecisionKey && dismissedDecisionKey !== currentDecisionKey) {
      setDismissedDecisionKey(null)
    }
  }, [confirmation?.status, currentDecisionKey, dismissedDecisionKey])

  useEffect(() => {
    if (decisionLoading) {
      return
    }
    if (
      dismissedDecisionKey &&
      confirmation?.status === 'needs_review' &&
      currentDecisionKey &&
      dismissedDecisionKey === currentDecisionKey
    ) {
      setDismissedDecisionKey(null)
    }
  }, [confirmation?.status, currentDecisionKey, decisionLoading, dismissedDecisionKey])

  if (!itinerary && !confirmation && !errorMessage) {
    return (
      <div className="px-4 pb-4">
        <div className="rounded-3xl border border-slate-200 bg-white px-4 py-5 text-sm text-slate-500 shadow-sm">
          方案生成完成后会展示在这里。
        </div>
      </div>
    )
  }

  if (!itinerary && errorMessage) {
    return (
      <div className="px-4 pb-4">
        <div className="rounded-3xl border border-rose-200 bg-rose-50 px-4 py-5 text-sm text-rose-600 shadow-sm">
          {errorMessage}
        </div>
      </div>
    )
  }

  return (
    <div className="px-4 pb-4">
      <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
        {confirmation?.status === 'needs_review' &&
        firstAction &&
        !(dismissedDecisionKey && currentDecisionKey && dismissedDecisionKey === currentDecisionKey) ? (
          <div className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <div className="font-semibold">需要你确认</div>
            <div className="mt-1 text-xs text-amber-800">
              {typeof firstDescription === 'string' ? firstDescription : '执行遇到备选替换，是否同意更改？'}
            </div>
            <div className="mt-3 flex gap-2">
              <div className="flex-1">
                <PrimaryButton
                  label="同意替换"
                  disabled={decisionLoading}
                  onClick={() => handleDecision('approve')}
                  className="h-10 text-sm"
                />
              </div>
              <button
                type="button"
                disabled={decisionLoading}
                onClick={() => handleDecision('reject')}
                className="h-10 flex-1 rounded-full border border-amber-300 bg-white text-sm font-semibold text-amber-900 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                拒绝替换
              </button>
            </div>
            {decisionLoading ? (
              <div className="mt-2 text-xs text-amber-800">已收到确认，正在继续执行…</div>
            ) : null}
          </div>
        ) : null}
        {dismissedDecisionKey && currentDecisionKey && dismissedDecisionKey === currentDecisionKey ? (
          <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <div className="font-semibold">已确认</div>
            <div className="mt-1 text-xs text-slate-600">继续执行中…</div>
          </div>
        ) : null}

        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="flex w-full items-center justify-between gap-3 text-left"
          aria-label={expanded ? '收起方案面板' : '展开方案面板'}
        >
          <div className="min-w-0">
            <div className="text-sm font-semibold text-slate-900">推荐方案</div>
            <div className="mt-1 text-xs text-slate-500">{summaryText}</div>
          </div>
          <span className="shrink-0 rounded-full bg-slate-100 p-2 text-slate-500">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
          </span>
        </button>

        {expanded ? (
          <>
            <div className="mt-4 max-h-[40vh] space-y-3 overflow-y-auto pr-1">
              {!hasPlans ? (
                <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
                  当前条件下暂时没有生成出合适方案，可以继续调整需求后重试。
                </div>
              ) : (
                plans.map((plan) => (
                  <div key={plan.plan_id} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-slate-900">{plan.title}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          总时长 {plan.total_duration_minutes} 分钟 · 预算 {plan.total_cost} 元
                        </div>
                      </div>
                      <div className="shrink-0 rounded-full bg-white px-3 py-1 text-xs text-slate-600 shadow-sm">
                        评分 {plan.average_score}
                      </div>
                    </div>

                    <div className="mt-3 space-y-2">
                      {plan.steps.slice(0, 4).map((step) => (
                        <div key={step.order_id} className="text-sm text-slate-700">
                          {step.order_id}. {step.item.display_name || step.item.name}
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>

            {confirmation ? (
              <div className="mt-4 rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                当前确认状态：{confirmation.status}
                {confirmation.reason ? ` · ${confirmation.reason}` : ''}
              </div>
            ) : null}

            {confirmation?.status === 'executed' && executionSummary ? (
              <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                <div className="font-semibold text-slate-900">执行结果</div>
                <div className="mt-2 space-y-2">
                  <div className="text-xs text-slate-500">已替换 {replacements.length} 项</div>
                  {replacements.length > 0 ? (
                    <div className="space-y-1">
                      {replacements.map((item: any, idx: number) => (
                        <div key={`${item.original_id ?? idx}`} className="text-sm">
                          {(item.original_name as string) || (item.original_id as string) || '原项'} →{' '}
                          {(item.new_item_name as string) || (item.new_item_id as string) || '备选'}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-500">未发生替换</div>
                  )}

                  <div className="pt-1 text-xs text-slate-500">失败 {failures.length} 项</div>
                  {failures.length > 0 ? (
                    <div className="space-y-1">
                      {failures.map((item: any, idx: number) => (
                        <div key={`${item.item_id ?? idx}`} className="text-sm text-rose-700">
                          {(item.item_name as string) || (item.item_id as string) || '预订失败'}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-500">无失败项</div>
                  )}
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  )
}

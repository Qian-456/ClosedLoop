import type { Confirmation, ItineraryPlan } from '../model/types'

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
        <div className="text-sm font-semibold text-slate-900">推荐方案</div>
        <div className="mt-1 text-xs text-slate-500">
          {hasPlans ? (itinerary?.status === 'ok' ? '已生成可执行方案' : '当前为降级或兜底结果') : '当前为降级或兜底结果'}
        </div>

        <div className="mt-4 space-y-3">
          {!hasPlans ? (
            <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
              当前条件下暂时没有生成出合适方案，可以继续调整需求后重试。
            </div>
          ) : (
            plans.map((plan) => (
              <div key={plan.plan_id} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">{plan.title}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      总时长 {plan.total_duration_minutes} 分钟 · 预算 {plan.total_cost} 元
                    </div>
                  </div>
                  <div className="rounded-full bg-white px-3 py-1 text-xs text-slate-600 shadow-sm">
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
      </div>
    </div>
  )
}

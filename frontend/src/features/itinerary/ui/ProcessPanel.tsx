import type { InvokeStreamProcessEvent } from '../model/types'

type Props = {
  items: InvokeStreamProcessEvent['data'][]
}

function renderSummary(item: InvokeStreamProcessEvent['data']): string {
  const raw = item.raw
  if (item.tool === 'plan_trip' && raw && typeof raw === 'object') {
    const result = (raw as { result?: { plans?: Array<{ total_cost?: number; total_duration_minutes?: number }> } }).result
    const plans = result?.plans ?? []
    const firstPlan = plans[0]
    if (firstPlan) {
      const budget = typeof firstPlan.total_cost === 'number' ? `预算 ${firstPlan.total_cost} 元` : null
      const duration =
        typeof firstPlan.total_duration_minutes === 'number'
          ? `总时长 ${firstPlan.total_duration_minutes} 分钟`
          : null
      return [item.summary, budget, duration].filter(Boolean).join(' · ')
    }
  }

  return item.summary
}

/**
 * Displays expandable process details grouped by tool execution.
 */
export function ProcessPanel({ items }: Props) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl bg-white/70 px-3 py-3 text-xs text-slate-500 shadow-sm">
        当前还没有过程详情。
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={`${item.tool}-${index}`} className="rounded-2xl bg-white/80 px-3 py-3 text-xs text-slate-600 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div className="font-medium text-slate-800">{item.tool}</div>
            <div className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
              {item.status}
            </div>
          </div>
          <div className="mt-1 leading-5 text-slate-600">{renderSummary(item)}</div>
        </div>
      ))}
    </div>
  )
}

import { useMemo, useState } from 'react'
import { Check, ChevronRight, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import type { ItineraryItemType, ItineraryPlanVariant, ItineraryStep, PlanCopywriting } from '../model/types'

type PlanCardProps = {
  plan: ItineraryPlanVariant
  copywriting?: PlanCopywriting
}

const TYPE_STYLES: Record<
  ItineraryItemType,
  { label: string; icon: string; bg: string; text: string; card: string }
> = {
  restaurant: {
    label: '餐',
    icon: '餐',
    bg: 'bg-orange-50',
    text: 'text-orange-600',
    card: 'border-orange-100 bg-orange-50/45',
  },
  activity: {
    label: '玩',
    icon: '玩',
    bg: 'bg-emerald-50',
    text: 'text-emerald-600',
    card: 'border-emerald-100 bg-emerald-50/45',
  },
  gift_shop: {
    label: '礼',
    icon: '礼',
    bg: 'bg-violet-50',
    text: 'text-violet-600',
    card: 'border-violet-100 bg-violet-50/55',
  },
  commute: {
    label: '通勤',
    icon: '车',
    bg: 'bg-slate-50',
    text: 'text-slate-600',
    card: 'border-slate-100 bg-slate-50/80',
  },
}

const formatDuration = (minutes: number) => {
  const safeMinutes = Number.isFinite(minutes) ? Math.max(0, Math.round(minutes)) : 0
  const h = Math.floor(safeMinutes / 60)
  const m = safeMinutes % 60
  if (h > 0 && m > 0) return `${h}h${m}m`
  if (h > 0) return `${h}h`
  return `${m}m`
}

const formatCost = (value: number) => `¥${Math.round(value)}`

const getStepCost = (step: ItineraryStep) =>
  Number(step.item.cost ?? 0) +
  Number(step.item.gift_price ?? 0) +
  Number(step.item.delivery_fee ?? 0)

const getModeLabel = (mode?: string | null) => {
  switch (mode) {
    case 'walking':
      return '步行'
    case 'driving':
      return '驾车'
    case 'taxi':
      return '打车'
    default:
      return '打车'
  }
}

const getDisplayName = (step: ItineraryStep) =>
  step.item.display_name || step.item.name || step.item.commute_to || '行程项目'

export function PlanCard({ plan, copywriting }: PlanCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const visibleSteps = useMemo(() => plan.steps.filter((step) => step.item.type !== 'commute'), [plan.steps])
  const reasons = copywriting?.pros_cons ?? []
  const score = Math.round(plan.experience_score ?? plan.average_score ?? 0)

  return (
    <article
      className={clsx(
        'cursor-pointer rounded-[8px] border bg-white p-4 shadow-sm transition',
        isExpanded ? 'border-blue-200 ring-1 ring-blue-100' : 'border-slate-200 hover:border-blue-100',
      )}
      onClick={() => setIsExpanded((value) => !value)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="max-w-full text-base font-bold leading-snug text-slate-950">{plan.title}</h3>
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-600">
              <Sparkles className="h-3.5 w-3.5" />
              推荐指数 {score}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-bold text-emerald-700">
            {formatCost(plan.total_cost)}
          </span>
          <ChevronRight className={clsx('h-5 w-5 text-slate-300 transition', isExpanded && 'rotate-90')} />
        </div>
      </div>

      {!isExpanded && reasons.length > 0 ? (
        <div className="mt-3 space-y-1.5">
          {reasons.slice(0, 2).map((text, index) => (
            <div key={`${text}-${index}`} className="flex items-start gap-2 text-sm leading-5 text-slate-700">
              <Check className="mt-0.5 h-4 w-4 shrink-0 stroke-[3] text-slate-800" />
              <span className="line-clamp-1">{text}</span>
            </div>
          ))}
        </div>
      ) : null}

      {isExpanded ? (
        <div className="mt-4">
          <div className="relative space-y-4">
            <div className="absolute bottom-3 left-[63px] top-3 w-px bg-slate-200" />
            {plan.steps.map((step, index) => (
              <TimelineStep key={step.order_id || `${step.item.id}-${index}`} step={step} index={index} />
            ))}
          </div>

          {reasons.length > 0 ? (
            <div className="mt-5 rounded-[8px] border border-slate-100 bg-white px-4 py-4">
              <div className="text-sm font-bold text-slate-950">为什么推荐这套</div>
              <div className="mt-3 space-y-2">
                {reasons.map((text, index) => (
                  <div key={`${text}-${index}`} className="flex items-start gap-2 text-sm leading-5 text-slate-700">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 stroke-[3] text-slate-800" />
                    <span>{text}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <>
          <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-2">
            {visibleSteps.map((step, index) => {
              const style = TYPE_STYLES[step.item.type]
              return (
                <div key={step.order_id || `${step.item.id}-${index}`} className="flex shrink-0 items-center gap-2">
                  <div className={clsx('flex min-w-[58px] flex-col items-center rounded-[8px] px-3 py-2', style.bg)}>
                    <span className={clsx('text-sm font-bold leading-none', style.text)}>{style.label}</span>
                    <span className="mt-1 text-xs font-medium text-slate-500">{step.duration_minutes}分钟</span>
                  </div>
                  {index < visibleSteps.length - 1 ? <ChevronRight className="h-4 w-4 text-slate-300" /> : null}
                </div>
              )
            })}
          </div>
          <div className="mt-1 flex items-center gap-4 text-xs text-slate-500">
            <span>
              总时长 <span className="font-bold text-slate-700">{formatDuration(plan.total_duration_minutes)}</span>
            </span>
            <span>
              总花费 <span className="font-bold text-slate-700">{formatCost(plan.total_cost)}</span>
            </span>
          </div>
        </>
      )}
    </article>
  )
}

function TimelineStep({ step, index }: { step: ItineraryStep; index: number }) {
  const isCommute = step.item.type === 'commute'
  const style = TYPE_STYLES[step.item.type]
  const cost = getStepCost(step)
  const startTime = step.start_time || '--:--'
  const endTime = step.end_time
  const mode = step.item.commute_recommended_mode || step.item.commute_mode

  return (
    <div className="relative grid grid-cols-[52px_1fr] gap-4">
      <div className="pt-4 text-right text-xs font-medium text-slate-500">{startTime}</div>
      <div className="absolute left-[60px] top-5 h-2 w-2 rounded-full bg-slate-300 ring-4 ring-white" />
      <div
        className={clsx(
          'min-w-0 rounded-[8px] border px-4 py-3',
          isCommute ? TYPE_STYLES.commute.card : style.card,
        )}
      >
        {isCommute ? (
          <div className="grid grid-cols-[28px_1fr_auto] items-start gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-xs font-bold text-slate-600">
              车
            </div>
            <div className="min-w-0">
              <div className="text-sm font-bold leading-6 text-slate-900">
                {step.item.commute_from || '上一站'} -&gt; {step.item.commute_to || '下一站'}
              </div>
              <div className="mt-1 text-xs leading-5 text-slate-500">
                推荐方式：{getModeLabel(mode)}
                {endTime ? ` · 预计 ${endTime} 到达` : ''}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-xs font-semibold leading-5 text-slate-600">{step.duration_minutes}分钟</div>
              {cost > 0 ? <div className="text-xs font-semibold text-slate-500">{formatCost(cost)}</div> : null}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-[28px_1fr_auto] items-start gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-xs font-bold text-slate-600">
              {style.icon}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-bold leading-6 text-slate-950">{getDisplayName(step)}</div>
              <div className="mt-1 text-xs leading-5 text-slate-500">
                {step.item.sub_name || step.note || step.item.location || `第 ${index + 1} 站`}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className={clsx('rounded-full px-3 py-1 text-xs font-bold', style.bg, style.text)}>
                {step.duration_minutes}分钟
              </div>
              <div className="mt-2 rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-700 shadow-sm">
                {formatCost(cost)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

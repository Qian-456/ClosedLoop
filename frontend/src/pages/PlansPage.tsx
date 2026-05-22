import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, ChevronRight } from 'lucide-react'
import { useItineraryStore } from '../features/itinerary/store/useItineraryStore'
import { formatDurationMinutes, formatMoney } from '../shared/lib/format'
import type {
  ItineraryItemType,
  ItineraryPlanVariant,
  PlanCopywriting,
} from '../features/itinerary/model/types'
import { pickFeaturedPlan } from '../features/itinerary/model/selectors'
import PlanAssistantDrawer from '../features/itinerary/ui/PlanAssistantDrawer'
import Skeleton from '../shared/ui/Skeleton'

function randomSessionId(): string {
  return `s_${Math.random().toString(16).slice(2)}_${Date.now()}`
}

function getTypeIcon(type: ItineraryItemType): { bg: string; text: string; label: string } {
  if (type === 'activity') return { bg: 'bg-emerald-50', text: 'text-emerald-600', label: '玩' }
  if (type === 'restaurant') return { bg: 'bg-orange-50', text: 'text-orange-600', label: '餐' }
  if (type === 'gift_shop') return { bg: 'bg-violet-50', text: 'text-violet-600', label: '礼' }
  return { bg: 'bg-slate-50', text: 'text-slate-500', label: '行' }
}

function toRecommendIndex(score: number): number | null {
  if (!Number.isFinite(score)) return null
  if (score <= 0) return 0
  if (score <= 1) return Math.round(score * 100)
  return Math.round(score)
}

function StepPills({ plan }: { plan: ItineraryPlanVariant }) {
  const steps = plan.steps.filter((s) => s.item.type !== 'commute').slice(0, 4)
  return (
    <div className="mt-3 flex items-center gap-2 overflow-hidden">
      {steps.map((s, idx) => {
        const icon = getTypeIcon(s.item.type)
        return (
          <div key={`${plan.plan_id}_${idx}`} className="flex items-center gap-2">
            <div className={`h-10 w-14 rounded-2xl ${icon.bg} flex flex-col items-center justify-center`}>
              <div className={`text-xs font-semibold ${icon.text}`}>{icon.label}</div>
              <div className="text-[11px] text-slate-500 leading-none">
                {Number.isFinite(s.duration_minutes) ? `${s.duration_minutes}分钟` : '--'}
              </div>
            </div>
            {idx < steps.length - 1 ? (
              <div className="text-slate-300 text-sm">›</div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function arrangePlansForDisplay(plans: ItineraryPlanVariant[]): ItineraryPlanVariant[] {
  if (plans.length <= 3) {
    const cheapest = [...plans].sort((a, b) => (a.total_cost ?? 0) - (b.total_cost ?? 0))[0]
    const plan2 = plans.find((p) => p.plan_id === 'plan_2')
    if (!plan2) return plans
    const remaining = plans.filter((p) => p.plan_id !== plan2.plan_id)
    const remainingSorted = remaining.slice().sort((a, b) => (a.total_cost ?? 0) - (b.total_cost ?? 0))
    const left = remainingSorted[0] ?? plan2
    const right =
      remainingSorted.length >= 2
        ? remainingSorted[remainingSorted.length - 1]
        : remainingSorted[0] ?? cheapest ?? plan2
    const used = new Set([left.plan_id, plan2.plan_id, right.plan_id])
    const fill = plans.find((p) => !used.has(p.plan_id))
    return [left, plan2, right].filter(Boolean).concat(fill ? [fill] : []).slice(0, 3)
  }

  const plan2 = plans.find((p) => p.plan_id === 'plan_2') ?? null
  const others = plans.filter((p) => p.plan_id !== 'plan_2')
  const cheapest = others.slice().sort((a, b) => (a.total_cost ?? 0) - (b.total_cost ?? 0))[0] ?? null
  const remainingAfterCheapest = others.filter((p) => p.plan_id !== cheapest?.plan_id)
  const priciest =
    remainingAfterCheapest.slice().sort((a, b) => (b.total_cost ?? 0) - (a.total_cost ?? 0))[0] ??
    (cheapest ? null : others.slice().sort((a, b) => (b.total_cost ?? 0) - (a.total_cost ?? 0))[0] ?? null)

  const used = new Set<string>()
  const ordered: ItineraryPlanVariant[] = []

  if (cheapest) {
    ordered.push(cheapest)
    used.add(cheapest.plan_id)
  }

  const middle =
    plan2 ??
    plans
      .slice()
      .sort(
        (a, b) =>
          (b.experience_score ?? b.average_score ?? 0) -
          (a.experience_score ?? a.average_score ?? 0),
      )[0] ??
    null
  if (middle && !used.has(middle.plan_id)) {
    ordered.push(middle)
    used.add(middle.plan_id)
  }

  if (priciest && !used.has(priciest.plan_id)) {
    ordered.push(priciest)
    used.add(priciest.plan_id)
  }

  for (const p of plans) {
    if (ordered.length >= 3) break
    if (used.has(p.plan_id)) continue
    ordered.push(p)
    used.add(p.plan_id)
  }

  return ordered.slice(0, 3)
}

export default function PlansPage() {
  const navigate = useNavigate()
  const state = useItineraryStore((s) => s.state)
  const storedUserInput = useItineraryStore((s) => s.userInput)
  const startSession = useItineraryStore((s) => s.startSession)
  const plans = state?.itinerary?.plans ?? []
  const copywritingPlans = state?.confirmation?.plans ?? null

  const featuredPlanId = useMemo(() => pickFeaturedPlan(plans), [plans])
  const displayPlans = useMemo(() => arrangePlansForDisplay(plans), [plans])

  const onOpen = (planId: string) => {
    navigate(`/app/plans/${planId}`)
  }

  if (!plans.length) {
    return (
      <>
        <main className="min-h-screen bg-[#F7F8FC] px-5 pt-14 pb-56">
          <div className="mx-auto max-w-[430px]">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">行程方案</h1>
            <p className="mt-2 text-sm text-slate-500">暂无方案，可返回重新生成</p>
          </div>
        </main>
        <PlanAssistantDrawer variant="plans" />
      </>
    )
  }

  return (
    <>
      <main className="min-h-screen bg-[#F7F8FC] px-5 pt-14 pb-56">
        <div className="mx-auto max-w-[430px]">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">行程方案</h1>
            <span className="text-xs font-medium px-2 py-1 rounded-full bg-sky-50 text-sky-700 border border-sky-100">
              Mock 展示
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">根据你的需求，已生成 3 套可比较方案</p>

          <div className="mt-5 space-y-4">
            {displayPlans.map((p, idx) => {
              const isFeatured = featuredPlanId != null && p.plan_id === featuredPlanId
              const copywriting =
                (copywritingPlans as Record<string, PlanCopywriting> | null)?.[p.plan_id] ?? null
              const displayTitle = copywriting?.plan_name?.trim()
                ? copywriting.plan_name
                : p.title?.trim()
                  ? p.title
                  : `方案 ${idx + 1}`
              const bullets = (copywriting?.pros_cons ?? []).slice(0, 2)
              return (
                <button
                  key={p.plan_id}
                  type="button"
                  onClick={() => onOpen(p.plan_id)}
                  className={[
                    'w-full text-left rounded-3xl bg-white p-4 shadow-sm border transition-colors',
                    isFeatured
                      ? 'border-blue-300 ring-2 ring-blue-500/10'
                      : 'border-slate-100 hover:border-slate-200',
                  ].join(' ')}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <div className="text-sm font-semibold text-slate-900">
                          {displayTitle}
                        </div>
                        {isFeatured ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 text-blue-700 border border-blue-100 px-2 py-1 text-[11px] font-semibold">
                            <Sparkles className="h-3.5 w-3.5" />
                            推荐指数 {toRecommendIndex(p.experience_score ?? p.average_score) ?? '--'}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-slate-50 text-slate-700 border border-slate-100 px-2 py-1 text-[11px] font-semibold">
                            推荐指数 {toRecommendIndex(p.experience_score ?? p.average_score) ?? '--'}
                          </span>
                        )}
                      </div>
                      <div className="mt-2 space-y-1">
                        {bullets.length ? (
                          bullets.map((b) => (
                            <div key={`${p.plan_id}_${b}`} className="text-xs text-slate-600">
                              {b}
                            </div>
                          ))
                        ) : (
                          <>
                            <Skeleton className="h-3 w-56" />
                            <Skeleton className="h-3 w-44" />
                          </>
                        )}
                      </div>
                    </div>
                    <div className="inline-flex items-center gap-2">
                      <div className="text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-full px-2 py-1">
                        {formatMoney(p.total_cost)}
                      </div>
                      <ChevronRight className="h-5 w-5 text-slate-300" />
                    </div>
                  </div>

                  <StepPills plan={p} />

                  <div className="mt-4 flex items-center gap-4 text-xs text-slate-600">
                    <div className="inline-flex items-center gap-1">
                      <span className="text-slate-400">总时长</span>
                      <span className="font-medium">
                        {formatDurationMinutes(p.total_duration_minutes)}
                      </span>
                    </div>
                    <div className="inline-flex items-center gap-1">
                      <span className="text-slate-400">总花费</span>
                      <span className="font-medium">{formatMoney(p.total_cost)}</span>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </main>
      <PlanAssistantDrawer
        variant="plans"
        onSubmit={(text) => {
          const base = (storedUserInput || state?.user_input || '').trim()
          const prompt = base
            ? `${base}\n\n我对这 3 个方案都不满意，请根据以下要求重新生成 3 套可比较方案：${text}`
            : `我对这 3 个方案都不满意，请根据以下要求重新生成 3 套可比较方案：${text}`
          startSession(randomSessionId(), prompt)
          navigate('/app/generating')
        }}
      />
    </>
  )
}

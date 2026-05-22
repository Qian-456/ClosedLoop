import { useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { useItineraryStore } from '../features/itinerary/store/useItineraryStore'
import type { ItineraryItemType, ItineraryPlanVariant, PlanCopywriting } from '../features/itinerary/model/types'
import { resolveItemSubtitle, resolveItemTitle } from '../features/itinerary/model/display'
import { minutesToTime, parseTimeToMinutes } from '../shared/lib/format'
import PrimaryButton from '../shared/ui/PrimaryButton'

function commuteModeIcon(mode: string | null | undefined): string {
  if (mode === 'walking') return '🚶'
  if (mode === 'taxi') return '🚕'
  if (mode === 'driving') return '🚗'
  return '🚗'
}

function getTypeMeta(type: ItineraryItemType): { pill: string; icon: string } {
  if (type === 'activity') return { pill: 'bg-emerald-50 text-emerald-700', icon: '🎠' }
  if (type === 'restaurant') return { pill: 'bg-orange-50 text-orange-700', icon: '🍽️' }
  if (type === 'gift_shop') return { pill: 'bg-violet-50 text-violet-700', icon: '🎁' }
  return { pill: 'bg-slate-50 text-slate-600', icon: '🚗' }
}

type TimelineStep = {
  start_time: string
  end_time: string
} & ItineraryPlanVariant['steps'][number]

function calcTimeline(plan: ItineraryPlanVariant, timePeriod: string): TimelineStep[] {
  const trimmed = timePeriod.trim()
  const m = /^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/.exec(trimmed)
  const parsed =
    m ? parseTimeToMinutes(m[1]) : /^\d{1,2}:\d{2}$/.test(trimmed) ? parseTimeToMinutes(trimmed) : null
  const startMinutes = parsed ?? 13 * 60

  let cursor = startMinutes
  return plan.steps.map((s) => {
    const start = cursor
    const dur = Number.isFinite(s.duration_minutes) ? s.duration_minutes : 0
    cursor += dur
    return {
      ...s,
      start_time: minutesToTime(start),
      end_time: minutesToTime(cursor),
    }
  })
}

export default function JourneyReadyPage() {
  const navigate = useNavigate()
  const { planId } = useParams()
  const state = useItineraryStore((s) => s.state)
  const plan = state?.itinerary?.plans?.find((p) => p.plan_id === planId) ?? null
  const timePeriod = state?.constraints?.time_period ?? ''
  const copywriting =
    (state?.confirmation?.plans as Record<string, PlanCopywriting> | undefined)?.[planId ?? ''] ??
    null

  const timeline = useMemo(() => (plan ? calcTimeline(plan, timePeriod) : []), [plan, timePeriod])

  if (!plan) {
    return (
      <main className="min-h-screen bg-[#F7F8FC] px-5 pt-10 pb-40">
        <div className="mx-auto max-w-[430px]">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="h-10 w-10 rounded-full bg-white border border-slate-100 flex items-center justify-center"
            aria-label="返回"
          >
            <ChevronLeft className="h-5 w-5 text-slate-700" />
          </button>
          <div className="mt-6 text-sm text-slate-500">方案不存在或未加载</div>
        </div>
      </main>
    )
  }

  return (
    <>
      <main className="min-h-screen bg-[#F7F8FC] px-5 pt-10 pb-40">
        <div className="mx-auto max-w-[430px]">
          <div className="flex items-start gap-3">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="h-10 w-10 rounded-full bg-white border border-slate-100 flex items-center justify-center"
              aria-label="返回"
            >
              <ChevronLeft className="h-5 w-5 text-slate-700" />
            </button>
            <div className="pt-1">
              <div className="text-xl font-semibold text-slate-900">开始行程</div>
              <div className="text-xs text-slate-500 mt-0.5">
                {copywriting?.plan_name?.trim()
                  ? copywriting.plan_name
                  : plan.title?.trim()
                    ? plan.title
                    : plan.plan_id}
              </div>
            </div>
          </div>

          <div className="mt-4 text-sm font-semibold text-slate-900">让我们准备开启今天的行程吧</div>

          <div className="mt-5 rounded-3xl bg-white p-4 shadow-sm border border-slate-100">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-slate-900">行程安排</div>
              <div className="text-xs text-slate-500">共 {timeline.length} 个行程</div>
            </div>

            <div className="mt-4 space-y-4">
              {timeline.map((s, idx) => {
                const meta =
                  s.item.type === 'commute'
                    ? { ...getTypeMeta(s.item.type), icon: commuteModeIcon(s.item.commute_mode) }
                    : getTypeMeta(s.item.type)
                return (
                  <div key={`${plan.plan_id}_${idx}`} className="flex gap-3">
                    <div className="w-12 flex flex-col items-center">
                      <div className="text-xs text-slate-500">{s.start_time}</div>
                      <div className="mt-2 h-2 w-2 rounded-full bg-slate-300" />
                      <div className="mt-2 h-full w-px bg-slate-200" />
                    </div>

                    <div
                      className={
                        s.item.type === 'gift_shop'
                          ? 'flex-1 rounded-2xl border border-violet-100 bg-violet-50 p-3 text-left'
                          : 'flex-1 rounded-2xl border border-slate-100 bg-slate-50 p-3 text-left'
                      }
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-lg leading-none">{meta.icon}</span>
                            <div className="text-sm font-semibold text-slate-900">
                              {resolveItemTitle(s.item)}
                            </div>
                          </div>
                          <div className="mt-2 text-[11px] text-slate-500">
                            {resolveItemSubtitle(s.item, { note: s.note, fallback: '预定/预定名额' })}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-semibold text-slate-900">
                            {Number.isFinite(s.duration_minutes) ? `${s.duration_minutes} 分钟` : '--'}
                          </div>
                          <div className="mt-1 inline-flex items-center gap-2">
                            {typeof s.item.cost === 'number' ? (
                              <div className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700">
                                ¥{Math.round(s.item.cost)}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </main>

      <div className="fixed bottom-0 left-0 right-0 z-30 mx-auto max-w-[430px] rounded-t-[28px] bg-white/90 px-5 pb-6 pt-4 shadow-2xl backdrop-blur border-t border-slate-100">
        <PrimaryButton label="开始流程" onClick={() => {}} />
      </div>
    </>
  )
}

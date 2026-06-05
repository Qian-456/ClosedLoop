import { useMemo, useState } from 'react'
import { CheckCircle2, ChevronLeft, Clock3, Flag, Footprints, Gift, Timer, Utensils, X } from 'lucide-react'
import type { ItineraryPlanVariant, ItineraryStep } from '../model/types'

type JourneyViewProps = {
  plan: ItineraryPlanVariant
  mode: 'active' | 'share'
  title?: string
  onClose?: () => void
}

type CommuteMode = 'walking' | 'taxi' | 'driving'

function toNumber(value: unknown) {
  const n = Number(value ?? 0)
  return Number.isFinite(n) ? n : 0
}

function formatCost(value: unknown) {
  const n = Number(value ?? 0)
  return `¥${Number.isFinite(n) ? Math.round(n) : 0}`
}

function formatDuration(value: unknown) {
  const safeMinutes = Math.max(0, Math.round(Number(value ?? 0)))
  const h = Math.floor(safeMinutes / 60)
  const m = safeMinutes % 60
  if (h > 0 && m > 0) return `${h}h${m}m`
  if (h > 0) return `${h}h`
  return `${m}分钟`
}

function getStepTitle(step: ItineraryStep) {
  const item = step.item
  if (item.type === 'commute') return `前往 ${item.commute_to || item.name || '下一站'}`
  return item.display_name || item.parent_name || item.name || '行程项目'
}

function getStepSubtitle(step: ItineraryStep, mode?: CommuteMode) {
  const item = step.item
  if (item.type === 'commute') {
    const modeLabel = mode === 'taxi' ? '打车' : mode === 'driving' ? '自驾' : '步行'
    return `推荐方式：${modeLabel}${step.end_time ? ` · 预计 ${step.end_time} 到达` : ''}`
  }
  return item.sub_name || item.name || step.note || '体验项目'
}

function getStepIcon(step: ItineraryStep) {
  if (step.item.type === 'restaurant') return Utensils
  if (step.item.type === 'activity') return Timer
  if (step.item.type === 'gift_shop') return Gift
  return Footprints
}

function getStepCost(step: ItineraryStep) {
  const total = toNumber(step.item.price_breakdown?.total)
  if (total > 0) return total
  return toNumber(step.item.cost)
}

function getMode(step: ItineraryStep, selected?: CommuteMode): CommuteMode {
  if (selected) return selected
  const raw = step.item.commute_recommended_mode || step.item.commute_mode || 'walking'
  if (raw === 'taxi' || raw === 'driving' || raw === 'walking') return raw
  return 'walking'
}

function getActionLabel(mode: CommuteMode) {
  if (mode === 'taxi') return '一键打车'
  if (mode === 'driving') return '驾车导航'
  return '步行导航'
}

function getActionMessage(step: ItineraryStep, mode: CommuteMode) {
  const from = step.item.commute_from || '当前位置'
  const to = step.item.commute_to || getStepTitle(step)
  if (mode === 'taxi') return '已生成 Mock 打车单，司机预计 3 分钟后到达'
  return `已打开 Mock 导航：从 ${from} 前往 ${to}`
}

function getAverageWaitMinutes(steps: ItineraryStep[]) {
  const waits = steps
    .filter((step) => step.item.type === 'restaurant' || step.item.type === 'activity')
    .map((step) => toNumber(step.item.duration_breakdown?.wait_minutes ?? step.item.expected_wait_minutes))
    .filter((value) => value > 0)
  if (!waits.length) return null
  return Math.round(waits.reduce((sum, value) => sum + value, 0) / waits.length)
}

export function JourneyView({ plan, mode, title = mode === 'active' ? '开始执行' : '分享行程', onClose }: JourneyViewProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [phase, setPhase] = useState<'heading' | 'arrived'>('heading')
  const [modeByIndex, setModeByIndex] = useState<Record<number, CommuteMode>>({})
  const [statusByIndex, setStatusByIndex] = useState<Record<number, string>>({})
  const averageWait = useMemo(() => getAverageWaitMinutes(plan.steps), [plan.steps])
  const isActive = mode === 'active'
  const isDone = currentIndex >= plan.steps.length

  const updateMode = (index: number, nextMode: CommuteMode) => {
    setModeByIndex((current) => ({ ...current, [index]: nextMode }))
    setStatusByIndex((current) => ({ ...current, [index]: '' }))
  }

  const advance = () => {
    const step = plan.steps[currentIndex]
    if (!step) return
    if (step.item.type === 'commute' && phase === 'heading') {
      setPhase('arrived')
      return
    }
    setPhase('heading')
    setCurrentIndex((value) => value + 1)
  }

  return (
    <main className="min-h-screen bg-[#F6F7FB]">
      <div className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-white/70 bg-white/80 px-4 backdrop-blur">
        {onClose ? (
          <button type="button" className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-600" onClick={onClose} aria-label="返回">
            <ChevronLeft className="h-5 w-5" />
          </button>
        ) : (
          <div className="h-9 w-9" />
        )}
        <div className="text-[15px] font-black text-slate-950">{title}</div>
        {onClose ? (
          <button type="button" className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500" onClick={onClose} aria-label="关闭">
            <X className="h-5 w-5" />
          </button>
        ) : (
          <div className="h-9 w-9" />
        )}
      </div>

      <div className="mx-auto max-w-[430px] px-5 pb-8 pt-4">
        <section className="rounded-[8px] border border-blue-100 bg-white px-5 py-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h1 className="text-2xl font-black leading-8 text-slate-950">{plan.title}</h1>
              <div className="mt-4 inline-flex rounded-full bg-blue-50 px-3 py-1 text-sm font-black text-blue-600">
                推荐指数 {Math.round(plan.experience_score ?? plan.average_score ?? 0)}
              </div>
            </div>
            <div className="rounded-full bg-emerald-50 px-5 py-3 text-2xl font-black text-emerald-700">
              {formatCost(plan.total_cost)}
            </div>
          </div>
          <div className="mt-4 space-y-2 text-sm font-semibold text-slate-500">
            <div className="flex items-center gap-2">
              <Clock3 className="h-4 w-4" />
              总时长 <span className="font-black text-slate-700">{formatDuration(plan.total_duration_minutes)}</span>
            </div>
            {averageWait !== null ? <div>平均等位 {averageWait} 分钟</div> : null}
          </div>
        </section>

        {isActive && isDone ? (
          <section className="mt-5 rounded-[8px] border border-emerald-100 bg-emerald-50 px-5 py-5 text-center">
            <Flag className="mx-auto h-8 w-8 text-emerald-500" />
            <div className="mt-3 text-lg font-black text-emerald-700">今日执行完成</div>
            <div className="mt-1 text-sm text-emerald-600">所有站点都已经完成。</div>
          </section>
        ) : null}

        <section className="mt-5 overflow-hidden rounded-[8px] border border-slate-200 bg-white">
          {plan.steps.map((step, index) => {
            const Icon = getStepIcon(step)
            const isCommute = step.item.type === 'commute'
            const selectedMode = getMode(step, modeByIndex[index])
            const cost = getStepCost(step)
            const isCurrent = isActive && index === currentIndex && !isDone
            const isPast = isActive && index < currentIndex
            const status = statusByIndex[index]

            return (
              <div
                key={step.order_id || `${step.item.id}-${index}`}
                className={[
                  'grid grid-cols-[84px_1fr] border-b border-slate-100 last:border-b-0',
                  isCurrent ? 'bg-blue-50/60' : isPast ? 'bg-slate-50/70 opacity-70' : 'bg-white',
                ].join(' ')}
              >
                <div className="relative px-3 py-5 text-right">
                  <div className="whitespace-pre-line text-base font-black leading-5 text-slate-950">
                    {step.start_time || '--:--'}
                    {step.end_time ? `\n${step.end_time}` : ''}
                  </div>
                  <div className="mt-2 text-xs font-semibold text-slate-500">
                    {Math.round(toNumber(step.duration_minutes))}分钟
                  </div>
                  <div className="absolute bottom-0 right-[-1px] top-0 w-px bg-slate-200" />
                  <div className="absolute right-[-6px] top-8 h-3 w-3 rounded-full bg-blue-200 ring-4 ring-white" />
                </div>

                <div className="px-4 py-5">
                  <div className="grid grid-cols-[42px_1fr_auto] items-start gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-lg font-black leading-6 text-slate-950">{getStepTitle(step)}</div>
                      <div className="mt-1 text-sm leading-5 text-slate-500">{getStepSubtitle(step, selectedMode)}</div>
                      {isCurrent ? (
                        <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-white px-2 py-1 text-xs font-black text-blue-600">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          {isCommute ? (phase === 'heading' ? '准备前往' : '已到达') : '开始体验'}
                        </div>
                      ) : null}
                    </div>
                    {cost > 0 && !isCommute ? <div className="pt-7 text-base font-black text-emerald-600">{formatCost(cost)}</div> : null}
                  </div>

                  {isCommute ? (
                    <div className="mt-4 space-y-3">
                      {isActive ? (
                        <div className="grid grid-cols-3 gap-2">
                          {(['walking', 'taxi', 'driving'] as const).map((item) => (
                            <button
                              key={item}
                              type="button"
                              className={[
                                'h-9 rounded-[8px] border text-xs font-black',
                                selectedMode === item ? 'border-blue-500 bg-blue-600 text-white' : 'border-blue-100 bg-white text-blue-600',
                              ].join(' ')}
                              onClick={() => updateMode(index, item)}
                            >
                              {item === 'taxi' ? '打车' : item === 'driving' ? '自驾' : '步行'}
                            </button>
                          ))}
                        </div>
                      ) : null}
                      <button
                        type="button"
                        className="h-10 min-w-[132px] rounded-full border border-blue-100 bg-blue-50 px-5 text-sm font-black text-blue-600"
                        onClick={() => setStatusByIndex((current) => ({ ...current, [index]: getActionMessage(step, selectedMode) }))}
                      >
                        {getActionLabel(selectedMode)}
                      </button>
                      {status ? (
                        <div className="rounded-[8px] border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
                          {status}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
            )
          })}
        </section>

        {isActive && !isDone ? (
          <div className="sticky bottom-0 -mx-5 mt-4 border-t border-white/70 bg-white/90 px-5 py-4 backdrop-blur">
            <button type="button" className="h-12 w-full rounded-[8px] bg-blue-600 text-base font-black text-white shadow-lg shadow-blue-100" onClick={advance}>
              {plan.steps[currentIndex]?.item.type === 'commute' && phase === 'heading'
                ? '已到达'
                : currentIndex >= plan.steps.length - 1
                  ? '完成执行'
                  : '完成本项，下一站'}
            </button>
          </div>
        ) : null}
      </div>
    </main>
  )
}

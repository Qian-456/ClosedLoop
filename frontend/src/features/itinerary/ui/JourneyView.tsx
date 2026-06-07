import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, ChevronLeft, Clock3, Flag, Footprints, Gift, Timer, Utensils, X } from 'lucide-react'
import type { ItineraryPlanVariant, ItineraryStep } from '../model/types'

type JourneyViewProps = {
  plan: ItineraryPlanVariant
  mode: 'active' | 'share'
  title?: string
  onClose?: () => void
  fitContainer?: boolean
  showHeader?: boolean
  paidCommuteStepKeys?: Set<string>
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

function getStepKey(step: ItineraryStep, index: number) {
  return step.order_id || `${step.item.id}-${index}`
}

function isPayableCommute(step: ItineraryStep) {
  if (step.item.type !== 'commute') return false
  const mode = step.item.commute_recommended_mode || step.item.commute_mode
  return (mode === 'taxi' || mode === 'driving') && getStepCost(step) > 0
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

export function JourneyView({
  plan,
  mode,
  title = mode === 'active' ? '开始执行' : '分享行程',
  onClose,
  fitContainer = false,
  showHeader = true,
  paidCommuteStepKeys,
}: JourneyViewProps) {
  const scrollRef = useRef<HTMLElement | null>(null)
  const storageKey = `journey_progress_${plan.plan_id}`

  const [currentIndex, setCurrentIndex] = useState<number>(() => {
    if (mode === 'share') return 0
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) return Number(JSON.parse(saved).currentIndex) || 0
    } catch {}
    return 0
  })

  const [phase, setPhase] = useState<'heading' | 'arrived'>(() => {
    if (mode === 'share') return 'heading'
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) return JSON.parse(saved).phase || 'heading'
    } catch {}
    return 'heading'
  })

  const [viewMode, setViewMode] = useState<'active' | 'share'>(mode)

  const [modeByIndex, setModeByIndex] = useState<Record<number, CommuteMode>>(() => {
    if (mode === 'share') return {}
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) return JSON.parse(saved).modeByIndex || {}
    } catch {}
    return {}
  })

  const [statusByIndex, setStatusByIndex] = useState<Record<number, string>>(() => {
    if (mode === 'share') return {}
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) return JSON.parse(saved).statusByIndex || {}
    } catch {}
    return {}
  })

  useEffect(() => {
    if (viewMode !== 'active') return
    const data = { currentIndex, phase, modeByIndex, statusByIndex }
    localStorage.setItem(storageKey, JSON.stringify(data))
  }, [currentIndex, phase, modeByIndex, statusByIndex, viewMode, storageKey])

  const handleReset = () => {
    if (window.confirm('确认重置当前行程进度？')) {
      setCurrentIndex(0)
      setPhase('heading')
      setModeByIndex({})
      setStatusByIndex({})
      localStorage.removeItem(storageKey)
    }
  }

  const [scrollThumb, setScrollThumb] = useState({ top: 16, height: 60, visible: false })
  const averageWait = useMemo(() => getAverageWaitMinutes(plan.steps), [plan.steps])
  const isActive = viewMode === 'active'
  const isDone = currentIndex >= plan.steps.length
  const effectivePaidCommuteStepKeys =
    paidCommuteStepKeys ??
    (isActive
      ? new Set(
          plan.steps
            .map((step, index) => ({ step, index }))
            .filter(({ step }) => isPayableCommute(step))
            .map(({ step, index }) => getStepKey(step, index)),
        )
      : undefined)
  const currentStep = plan.steps[currentIndex] ?? null
  const unusedCurrentStepIsPaidCommute = currentStep
    ? effectivePaidCommuteStepKeys?.has(getStepKey(currentStep, currentIndex)) ?? false
    : false
  const headerTitle = viewMode === 'active' ? '开始执行' : title

  const syncScrollThumb = () => {
    const el = scrollRef.current
    if (!el) return
    const scrollable = el.scrollHeight > el.clientHeight + 8
    if (!scrollable) {
      setScrollThumb((current) => ({ ...current, visible: false }))
      return
    }
    const trackTop = 18
    const trackHeight = Math.max(80, el.clientHeight - 36)
    const height = Math.max(46, Math.round((el.clientHeight / el.scrollHeight) * trackHeight))
    const maxTop = trackTop + trackHeight - height
    const progress = el.scrollTop / Math.max(1, el.scrollHeight - el.clientHeight)
    setScrollThumb({ top: Math.round(trackTop + (maxTop - trackTop) * progress), height, visible: true })
  }

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    syncScrollThumb()
    const resizeObserver = new ResizeObserver(syncScrollThumb)
    resizeObserver.observe(el)
    resizeObserver.observe(el.firstElementChild ?? el)
    return () => resizeObserver.disconnect()
  }, [plan.steps.length, viewMode, isDone])

  const updateMode = (index: number, nextMode: CommuteMode) => {
    const step = plan.steps[index]
    if (step && effectivePaidCommuteStepKeys?.has(getStepKey(step, index))) return
    setModeByIndex((current) => ({ ...current, [index]: nextMode }))
    setStatusByIndex((current) => ({ ...current, [index]: '' }))
  }

  const advance = () => {
    const step = plan.steps[currentIndex]
    if (!step) return
    if (false && unusedCurrentStepIsPaidCommute && phase === 'heading') {
      setStatusByIndex((current) => ({ ...current, [currentIndex]: '该通勤订单已支付，可在支付订单中查看当前订单状态。' }))
      return
    }
    if (step.item.type === 'commute' && phase === 'heading') {
      setPhase('arrived')
      return
    }
    setPhase('heading')
    setCurrentIndex((value) => value + 1)
  }

  return (
    <div className={['relative overflow-hidden bg-[#F6F7FB]', fitContainer ? 'h-full' : 'h-full min-h-screen'].join(' ')}>
      <main
        ref={scrollRef}
        className={[
          'h-full overflow-y-auto bg-[#F6F7FB] [scrollbar-color:#CBD5E1_transparent] [scrollbar-width:thin]',
          fitContainer ? '' : 'min-h-screen',
        ].join(' ')}
        onScroll={syncScrollThumb}
      >
      {showHeader ? (
        <div className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-white/70 bg-white/80 px-4 backdrop-blur">
          {onClose ? (
            <button type="button" className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-600" onClick={onClose} aria-label="返回">
              <ChevronLeft className="h-5 w-5" />
            </button>
          ) : (
            <div className="h-9 w-9" />
          )}
          <div className="text-[15px] font-black text-slate-950">{headerTitle}</div>
          <div className="flex items-center gap-1">
            {isActive && (currentIndex > 0 || phase !== 'heading' || Object.keys(modeByIndex).length > 0 || Object.keys(statusByIndex).length > 0) ? (
              <button 
                type="button" 
                className="flex h-8 items-center justify-center rounded-full bg-slate-100 px-3 text-xs font-bold text-slate-600 hover:bg-slate-200"
                onClick={handleReset}
              >
                重置
              </button>
            ) : null}
            {onClose ? (
              <button type="button" className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500" onClick={onClose} aria-label="关闭">
                <X className="h-5 w-5" />
              </button>
            ) : (
              <div className="h-9 w-9" />
            )}
          </div>
        </div>
      ) : null}

      <div className="mx-auto max-w-[430px] px-5 pb-32 pt-4">
        <section className="rounded-[8px] border border-blue-100 bg-white px-5 py-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h1 className="text-2xl font-black leading-8 text-slate-950">{plan.title}</h1>
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

        {viewMode === 'share' ? (
          <button
            type="button"
            className="mt-4 flex h-12 w-full items-center justify-center rounded-[8px] bg-blue-600 text-base font-black text-white shadow-lg shadow-blue-100"
            onClick={() => {
              setViewMode('active')
              setCurrentIndex(0)
              setPhase('heading')
            }}
          >
            开始执行
          </button>
        ) : null}

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
            const isPaidCommute =
              (effectivePaidCommuteStepKeys?.has(getStepKey(step, index)) ?? false) ||
              (isCommute &&
                typeof status === 'string' &&
                (status.includes('订单已支付') || status.includes('已支付') || status.includes('宸叉敮')))
            const paidCommuteStatus = '该通勤订单已支付，可在支付订单中查看当前订单状态。'
            const displayStatus = status || (isPaidCommute ? paidCommuteStatus : '')

            return (
              <div
                key={step.order_id || `${step.item.id}-${index}`}
                className={[
                  'grid grid-cols-[84px_1fr] border-b border-slate-100 last:border-b-0',
                  isCurrent
                    ? 'bg-blue-50/80 ring-1 ring-inset ring-blue-200'
                    : isPast
                      ? 'bg-slate-50 text-slate-400 opacity-65'
                      : 'bg-white',
                ].join(' ')}
              >
                <div className="relative px-3 py-5 text-right">
                  <div className={['whitespace-pre-line text-base font-black leading-5', isPast ? 'text-slate-400' : 'text-slate-950'].join(' ')}>
                    {step.start_time || '--:--'}
                    {step.end_time ? `\n${step.end_time}` : ''}
                  </div>
                  <div className="mt-2 text-xs font-semibold text-slate-500">
                    {Math.round(toNumber(step.duration_minutes))}分钟
                  </div>
                  <div className="absolute bottom-0 right-[-1px] top-0 w-px bg-slate-200" />
                  <div
                    className={[
                      'absolute right-[-6px] top-8 flex h-3 w-3 items-center justify-center rounded-full ring-4 ring-white',
                      isPast ? 'bg-slate-300' : isCurrent ? 'bg-blue-600' : 'bg-blue-200',
                    ].join(' ')}
                  />
                </div>

                <div className="px-4 py-5">
                  <div className="grid grid-cols-[42px_1fr_auto] items-start gap-3">
                    <div
                      className={[
                        'flex h-11 w-11 items-center justify-center rounded-full',
                        isPast ? 'bg-slate-100 text-slate-400' : isCurrent ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-600',
                      ].join(' ')}
                    >
                      {isPast ? <CheckCircle2 className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                    </div>
                    <div className="min-w-0">
                      <div className={['text-lg font-black leading-6', isPast ? 'text-slate-500' : 'text-slate-950'].join(' ')}>
                        {getStepTitle(step)}
                      </div>
                      <div className={['mt-1 text-sm leading-5', isPast ? 'text-slate-400' : 'text-slate-500'].join(' ')}>
                        {getStepSubtitle(step, selectedMode)}
                      </div>
                      {isCurrent ? (
                        <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-white px-2 py-1 text-xs font-black text-blue-600">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          {isCommute ? (phase === 'heading' ? '准备前往' : '已到达') : '开始体验'}
                        </div>
                      ) : isPast ? (
                        <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs font-black text-slate-500">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          已完成
                        </div>
                      ) : null}
                    </div>
                    {cost > 0 && !isCommute ? <div className="pt-7 text-base font-black text-emerald-600">{formatCost(cost)}</div> : null}
                  </div>

                  {isCommute ? (
                    <div className="mt-4 space-y-3">
                      {isActive && !isPaidCommute ? (
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
                        onClick={() => setStatusByIndex((current) => ({ ...current, [index]: isPaidCommute ? paidCommuteStatus : getActionMessage(step, selectedMode) }))}
                      >
                        {isPaidCommute ? '查看订单' : getActionLabel(selectedMode)}
                      </button>
                      {displayStatus ? (
                        <div className="rounded-[8px] border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
                          {displayStatus}
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
      {scrollThumb.visible ? (
        <div className="pointer-events-none absolute right-1.5 top-0 z-40 h-full w-2">
          <div
            className="absolute right-0 w-1.5 rounded-full bg-slate-400/75 shadow-sm"
            style={{ top: scrollThumb.top, height: scrollThumb.height }}
          />
        </div>
      ) : null}
    </div>
  )
}

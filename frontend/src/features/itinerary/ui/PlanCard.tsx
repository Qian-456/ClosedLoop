import { useState, type ReactNode } from 'react'
import { Car, Check, ChevronRight, Clock3, Footprints, Gift, MapPinned, Navigation, Timer, Utensils, Wallet, X } from 'lucide-react'
import clsx from 'clsx'
import type { ItineraryItem, ItineraryItemType, ItineraryPlanVariant, ItineraryStep, PlanCopywriting } from '../model/types'

type PlanCardProps = {
  plan: ItineraryPlanVariant
  copywriting?: PlanCopywriting
  selectedStep: ItineraryStep | null
  onOpenStep: (step: ItineraryStep) => void
  onCloseStep: () => void
  onCollapsePanel?: () => void
  paidCommuteStepKeys?: Set<string>
}

type TypeStyle = {
  label: string
  Icon: typeof Utensils
  bg: string
  text: string
  dot: string
  accent: string
}

const TYPE_STYLES: Record<ItineraryItemType, TypeStyle> = {
  restaurant: {
    label: '餐',
    Icon: Utensils,
    bg: 'bg-orange-50',
    text: 'text-orange-600',
    dot: 'bg-orange-200',
    accent: 'text-orange-600',
  },
  activity: {
    label: '玩',
    Icon: Timer,
    bg: 'bg-violet-50',
    text: 'text-violet-600',
    dot: 'bg-violet-200',
    accent: 'text-violet-600',
  },
  gift_shop: {
    label: '礼',
    Icon: Gift,
    bg: 'bg-rose-50',
    text: 'text-rose-600',
    dot: 'bg-rose-200',
    accent: 'text-rose-600',
  },
  commute: {
    label: '行',
    Icon: Footprints,
    bg: 'bg-blue-50',
    text: 'text-blue-600',
    dot: 'bg-blue-200',
    accent: 'text-blue-600',
  },
}

const toNumber = (value: unknown) => {
  const n = Number(value ?? 0)
  return Number.isFinite(n) ? n : 0
}

const formatCost = (value: number) => `¥${Math.round(value)}`

const formatDuration = (minutes: number) => {
  const safeMinutes = Number.isFinite(minutes) ? Math.max(0, Math.round(minutes)) : 0
  const h = Math.floor(safeMinutes / 60)
  const m = safeMinutes % 60
  if (h > 0 && m > 0) return `${h}h${m}m`
  if (h > 0) return `${h}h`
  return `${m}分钟`
}

const getStepCost = (step: ItineraryStep) => {
  const total = toNumber(step.item.price_breakdown?.total)
  if (total > 0) return total
  return toNumber(step.item.cost)
}

const getStepKey = (step: ItineraryStep, index: number) => step.order_id || `${step.item.id}-${index}`

const getModeLabel = (mode?: string | null) => {
  switch (mode) {
    case 'walking':
      return '步行'
    case 'driving':
      return '自驾'
    case 'taxi':
      return '打车'
    default:
      return '自动'
  }
}

const getCommuteActionLabel = (mode?: string | null) => {
  if (mode === 'taxi') return '一键打车'
  if (mode === 'driving') return '驾车导航'
  return '步行导航'
}

const getCommuteActionMessage = (mode: string, from: string, to: string) => {
  if (mode === 'taxi') return `已生成 Mock 打车单，司机预计 3 分钟后到达`
  return `已打开 Mock 导航：从 ${from} 前往 ${to}`
}

const getCommuteOptionMeta = (step: ItineraryStep, mode: 'walking' | 'taxi' | 'driving') => {
  const option = step.item.commute_options?.find((x) => x.mode === mode)
  return {
    minutes: option?.time_minutes ?? toNumber(step.duration_minutes),
    cost: option?.cost ?? (mode === 'taxi' || mode === 'driving' ? getStepCost(step) : 0),
  }
}

const getDisplayName = (step: ItineraryStep) =>
  step.item.display_name || step.item.parent_name || step.item.name || step.item.commute_to || '行程项目'

const getSubName = (item: ItineraryItem) => item.sub_name || item.name

const getStepTimeRange = (step: ItineraryStep) => {
  if (step.start_time && step.end_time) return `${step.start_time}\n${step.end_time}`
  if (step.start_time) return step.start_time
  return '--:--'
}

const compactRows = (rows: Array<[string, number]>): Array<[string, number]> =>
  rows.filter(([, value]) => Number.isFinite(value) && value > 0)

const getStepWaitMinutes = (step: ItineraryStep) => toNumber(step.item.duration_breakdown?.wait_minutes ?? step.item.expected_wait_minutes)

const getStepBaseMinutes = (step: ItineraryStep) => toNumber(step.item.duration_breakdown?.base_minutes)

const getStepTotalMinutesForDisplay = (step: ItineraryStep) => {
  const waitMinutes = getStepWaitMinutes(step)
  const baseMinutes = getStepBaseMinutes(step)
  if (waitMinutes > 0 && baseMinutes > 0) return baseMinutes + waitMinutes

  const totalFromBreakdown = toNumber(step.item.duration_breakdown?.total_minutes)
  if (totalFromBreakdown > 0) return totalFromBreakdown

  return toNumber(step.duration_minutes)
}

const getAverageWaitMinutes = (steps: ItineraryStep[]) => {
  const waitMinutes = steps
    .filter((step) => step.item.type === 'restaurant' || step.item.type === 'activity')
    .map((step) => getStepWaitMinutes(step))
    .filter((value) => value > 0)

  if (waitMinutes.length === 0) return null

  const sum = waitMinutes.reduce((acc, value) => acc + value, 0)
  return Math.round(sum / waitMinutes.length)
}

function DetailRow({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={clsx('flex items-center justify-between gap-4 text-sm leading-7', strong && 'border-t border-dashed border-slate-200 pt-2')}>
      <span className={strong ? 'font-bold text-slate-950' : 'text-slate-500'}>{label}</span>
      <span className={strong ? 'font-bold text-orange-600' : 'font-semibold text-slate-700'}>{value}</span>
    </div>
  )
}

function DetailSection({
  icon,
  title,
  children,
}: {
  icon: ReactNode
  title: string
  children: ReactNode
}) {
  return (
    <section className="rounded-[12px] border border-slate-200 bg-white px-4 py-4">
      <div className="mb-3 flex items-center gap-2 text-base font-bold text-slate-950">
        <span className="flex h-7 w-7 items-center justify-center rounded-[8px] bg-slate-50">{icon}</span>
        {title}
      </div>
      {children}
    </section>
  )
}

function StepDetailSheet({
  step,
  onClose,
  onCollapsePanel,
  isPaidCommute,
}: {
  step: ItineraryStep
  onClose: () => void
  onCollapsePanel?: () => void
  isPaidCommute?: boolean
}) {
  const item = step.item
  const style = TYPE_STYLES[item.type]
  const stepCost = getStepCost(step)
  const priceRows = compactRows([
    [item.type === 'restaurant' ? '套餐' : item.type === 'activity' ? '门票' : '基础费用', toNumber(item.price_breakdown?.base_price)],
    ['礼品', toNumber(item.price_breakdown?.gift_price)],
    ['配送', toNumber(item.price_breakdown?.delivery_fee)],
    ['通勤', toNumber(item.price_breakdown?.commute_fee)],
  ])
  const durationRows = compactRows([
    [item.type === 'restaurant' ? '基础用餐' : item.type === 'activity' ? '基础体验' : '基础时长', toNumber(item.duration_breakdown?.base_minutes)],
    ['预计排队', toNumber(item.duration_breakdown?.wait_minutes ?? item.expected_wait_minutes)],
    ['转场缓冲', toNumber(item.duration_breakdown?.buffer_minutes)],
  ])
  const totalMinutes = toNumber(item.duration_breakdown?.total_minutes || step.duration_minutes)
  const intro = item.intro || (item as any).description || ''
  const recommendation = item.features || intro
  const Icon = style.Icon
  const collapsePanel = onCollapsePanel ?? onClose
  const isCommute = item.type === 'commute'
  const [commuteMode, setCommuteMode] = useState<'walking' | 'taxi' | 'driving'>(
    (item.commute_recommended_mode || item.commute_mode || 'walking') as 'walking' | 'taxi' | 'driving',
  )
  const [commuteStatus, setCommuteStatus] = useState('')
  const commuteFrom = item.commute_from || '当前位置'
  const commuteTo = item.commute_to || getDisplayName(step)
  const commuteMeta = getCommuteOptionMeta(step, commuteMode)

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-slate-950/55 backdrop-blur-[2px]" onClick={onClose}>
      <div
        className="max-h-[86vh] w-full overflow-y-auto rounded-t-[28px] bg-white px-5 pb-6 pt-4 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="mx-auto mb-5 block h-6 w-20 rounded-full"
          aria-label="收起全部推荐方案"
          onClick={collapsePanel}
        >
          <span className="mx-auto block h-1.5 w-14 rounded-full bg-slate-300" />
        </button>
        <button
          type="button"
          className="absolute right-5 top-5 flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500"
          onClick={onClose}
          aria-label="关闭详情"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="grid grid-cols-[54px_1fr_auto] items-start gap-3 pr-10">
          <div className={clsx('flex h-12 w-12 items-center justify-center rounded-full', style.bg, style.text)}>
            <Icon className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <h3 className="text-xl font-bold leading-7 text-slate-950">{getDisplayName(step)}</h3>
            {item.type !== 'commute' && getSubName(item) ? (
              <div className={clsx('mt-2 inline-flex max-w-full rounded-[8px] px-2 py-1 text-xs font-semibold', style.bg, style.text)}>
                <span className="truncate">{getSubName(item)}</span>
              </div>
            ) : null}
          </div>
          {stepCost > 0 ? <div className={clsx('pt-7 text-xl font-bold', style.accent)}>{formatCost(stepCost)}</div> : null}
        </div>

        <div className="mt-6 space-y-4">
          {isCommute ? (
            <DetailSection icon={<MapPinned className="h-4 w-4 text-blue-500" />} title="转场操作">
              <div className="space-y-3">
                <div className="rounded-[8px] bg-blue-50 px-3 py-3 text-sm leading-6 text-slate-700">
                  <div>
                    <span className="font-semibold text-slate-950">出发：</span>
                    {commuteFrom}
                  </div>
                  <div>
                    <span className="font-semibold text-slate-950">到达：</span>
                    {commuteTo}
                  </div>
                  <div className="text-xs font-semibold text-blue-600">
                    预计 {Math.round(commuteMeta.minutes)} 分钟
                    {commuteMeta.cost > 0 ? ` · ${formatCost(commuteMeta.cost)}` : ''}
                  </div>
                </div>

                {!isPaidCommute ? <div className="grid grid-cols-3 gap-2">
                  {(['walking', 'taxi', 'driving'] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      className={clsx(
                        'h-10 rounded-[8px] border text-sm font-bold',
                        commuteMode === mode
                          ? 'border-blue-500 bg-blue-600 text-white'
                          : 'border-blue-100 bg-white text-blue-600',
                      )}
                      onClick={() => {
                        setCommuteMode(mode)
                        setCommuteStatus('')
                      }}
                    >
                      {getModeLabel(mode)}
                    </button>
                  ))}
                </div> : null}

                <button
                  type="button"
                  className="flex h-12 w-full items-center justify-center gap-2 rounded-[8px] bg-blue-600 text-base font-bold text-white shadow-lg shadow-blue-100"
                  onClick={() => setCommuteStatus(isPaidCommute ? '该通勤订单已支付，可在支付订单中查看当前订单状态。' : getCommuteActionMessage(commuteMode, commuteFrom, commuteTo))}
                >
                  {commuteMode === 'taxi' ? <Car className="h-5 w-5" /> : <Navigation className="h-5 w-5" />}
                  {isPaidCommute ? '查看订单状态' : getCommuteActionLabel(commuteMode)}
                </button>

                {commuteStatus ? (
                  <div className="rounded-[8px] border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
                    {commuteStatus}
                  </div>
                ) : null}
              </div>
            </DetailSection>
          ) : null}

          {recommendation ? (
            <DetailSection icon={<Check className="h-4 w-4 text-amber-500" />} title="推荐理由">
              <p className="text-sm leading-7 text-slate-600">{recommendation}</p>
            </DetailSection>
          ) : null}

          {(priceRows.length > 0 || stepCost > 0) && (
            <DetailSection icon={<Wallet className="h-4 w-4 text-orange-500" />} title="费用组成">
              <div className="space-y-1">
                {priceRows.map(([label, value]) => (
                  <DetailRow key={label} label={label} value={formatCost(value)} />
                ))}
                <DetailRow label="合计" value={formatCost(stepCost)} strong />
              </div>
            </DetailSection>
          )}

          {(durationRows.length > 0 || totalMinutes > 0) && (
            <DetailSection icon={<Clock3 className="h-4 w-4 text-emerald-500" />} title="时间组成">
              <div className="space-y-1">
                {durationRows.map(([label, value]) => (
                  <DetailRow key={label} label={label} value={`${Math.round(value)} 分钟`} />
                ))}
                {totalMinutes > 0 ? <DetailRow label="总时长" value={`${Math.round(totalMinutes)} 分钟`} strong /> : null}
              </div>
            </DetailSection>
          )}

          {intro && intro !== recommendation ? (
            <DetailSection icon={<Icon className={clsx('h-4 w-4', style.text)} />} title="内容说明">
              <p className="text-sm leading-7 text-slate-600">{intro}</p>
            </DetailSection>
          ) : null}
        </div>

        <button
          type="button"
          className="mt-6 h-14 w-full rounded-full bg-blue-600 text-base font-bold text-white shadow-lg shadow-blue-100"
          onClick={onClose}
        >
          返回行程
        </button>
      </div>
    </div>
  )
}

function TimelineRow({
  step,
  index,
  isPaidCommute,
  onOpenStep,
}: {
  step: ItineraryStep
  index: number
  isPaidCommute?: boolean
  onOpenStep: (step: ItineraryStep) => void
}) {
  const item = step.item
  const style = TYPE_STYLES[item.type]
  const Icon = style.Icon
  const isCommute = item.type === 'commute'
  const cost = getStepCost(step)
  const mode = item.commute_recommended_mode || item.commute_mode
  const [paidCommuteStatus, setPaidCommuteStatus] = useState('')
  const waitMinutes = getStepWaitMinutes(step)
  const totalMinutes = getStepTotalMinutesForDisplay(step)
  const durationLabel = waitMinutes > 0 && !isCommute ? `总时长 ${totalMinutes}分钟（含等位${waitMinutes}分钟）` : `${toNumber(step.duration_minutes)}分钟`

  return (
    <div className="grid grid-cols-[70px_1fr] border-b border-slate-100 last:border-b-0">
      <div className="relative px-3 py-4 text-right">
        <div className="whitespace-pre-line text-sm font-bold leading-5 text-slate-950">{getStepTimeRange(step)}</div>
        <div className="mt-1 text-xs text-slate-500">{durationLabel}</div>
        <div className="absolute bottom-0 right-[-1px] top-0 w-px bg-slate-200" />
        <div className={clsx('absolute right-[-5px] top-8 h-2.5 w-2.5 rounded-full ring-4 ring-white', style.dot)} />
      </div>

      <div className="grid grid-cols-[40px_1fr_auto] items-start gap-3 px-4 py-4">
        <div className={clsx('flex h-10 w-10 items-center justify-center rounded-full', style.bg, style.text)}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="text-base font-bold leading-6 text-slate-950">
            {isCommute ? `前往 ${item.commute_to || getDisplayName(step)}` : getDisplayName(step)}
          </div>
          <div className="mt-1 text-sm leading-5 text-slate-500">
            {isCommute ? (
              <>
                推荐方式：{getModeLabel(mode)}
                {step.end_time ? ` · 预计 ${step.end_time} 到达` : ''}
              </>
            ) : (
              getSubName(item) || step.note || `第 ${index + 1} 站`
            )}
          </div>
          {waitMinutes > 0 && !isCommute ? (
            <div className="mt-1.5 inline-flex items-center gap-1 rounded-[6px] bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-600">
              <span className="text-[10px]">🔥</span> 预估等位 {waitMinutes} 分钟
            </div>
          ) : null}
          <div className="mt-3">
            <button
              type="button"
              className={clsx(
                'h-9 min-w-[112px] rounded-full border px-5 text-sm font-semibold',
                isCommute ? 'border-blue-100 bg-blue-50 text-blue-600' : 'border-blue-100 bg-white text-blue-600',
              )}
              onClick={() => {
                if (isPaidCommute) {
                  setPaidCommuteStatus('订单已支付')
                  return
                }
                onOpenStep(step)
              }}
            >
              {isCommute ? (isPaidCommute ? '查看订单状态' : getCommuteActionLabel(mode)) : '详情'}
            </button>
            {paidCommuteStatus ? (
              <div className="mt-2 text-xs font-semibold text-emerald-600">{paidCommuteStatus}</div>
            ) : null}
          </div>
        </div>
        <div className="flex items-start gap-2">
          {cost > 0 && !isCommute ? <div className="pt-12 text-base font-bold text-emerald-600">{formatCost(cost)}</div> : null}
          <ChevronRight className="mt-2 h-5 w-5 text-slate-300" />
        </div>
      </div>
    </div>
  )
}

export function PlanCard({
  plan,
  copywriting,
  selectedStep,
  onOpenStep,
  onCloseStep,
  onCollapsePanel,
  paidCommuteStepKeys,
}: PlanCardProps) {
  const reasons = copywriting?.pros_cons ?? []
  const averageWaitMinutes = getAverageWaitMinutes(plan.steps)
  const selectedStepIndex = selectedStep ? plan.steps.findIndex((step) => step === selectedStep) : -1
  const selectedStepIsPaidCommute =
    selectedStep && selectedStepIndex >= 0 ? paidCommuteStepKeys?.has(getStepKey(selectedStep, selectedStepIndex)) : false

  return (
    <>
      <article className="rounded-[8px] border border-blue-100 bg-white p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="text-lg font-bold leading-7 text-slate-950">{plan.title}</h3>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-500">
              <span className="inline-flex items-center gap-1">
                <Clock3 className="h-4 w-4" />
                总时长 <b className="text-slate-700">{formatDuration(toNumber(plan.total_duration_minutes))}</b>
              </span>
              {typeof averageWaitMinutes === 'number' ? <span>平均等位 {averageWaitMinutes} 分钟</span> : null}
            </div>
          </div>
          <div className="rounded-full bg-emerald-50 px-4 py-2 text-lg font-bold text-emerald-700">
            {formatCost(toNumber(plan.total_cost))}
          </div>
        </div>

        {reasons.length > 0 ? (
          <div className="mt-4 space-y-1.5">
            {reasons.slice(0, 2).map((text, index) => (
              <div key={`${text}-${index}`} className="flex items-start gap-2 text-sm leading-5 text-slate-600">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-slate-700" />
                <span className="line-clamp-1">{text}</span>
              </div>
            ))}
          </div>
        ) : null}
      </article>

      <div className="mt-4 overflow-hidden rounded-[8px] border border-slate-200 bg-white">
        {plan.steps.map((step, index) => (
          <TimelineRow
            key={getStepKey(step, index)}
            step={step}
            index={index}
            isPaidCommute={paidCommuteStepKeys?.has(getStepKey(step, index))}
            onOpenStep={onOpenStep}
          />
        ))}
      </div>

      {selectedStep ? (
        <StepDetailSheet
          step={selectedStep}
          isPaidCommute={selectedStepIsPaidCommute}
          onClose={onCloseStep}
          onCollapsePanel={onCollapsePanel}
        />
      ) : null}
    </>
  )
}

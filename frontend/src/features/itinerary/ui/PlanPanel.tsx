import { useMemo, useState } from 'react'
import { CheckCircle2, ChevronDown, ChevronLeft, Clock3, Copy, CreditCard, Delete, Flag, MapPinned, Play, Share2, ShieldCheck, Ticket, X } from 'lucide-react'
import { useItineraryStore } from '../store/useItineraryStore'
import { PlanCard } from './PlanCard'
import { JourneyView } from './JourneyView'
import { commitMockPayment } from '../api/invoke'

import type { Confirmation, ItineraryPlan, ItineraryPlanVariant, ItineraryStep, ThreePlansCopywriting } from '../model/types'

type Props = {
  itinerary?: ItineraryPlan | null
  confirmation?: Confirmation | null
  errorMessage?: string | null
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

function PlanSummaryCard({
  plan,
  onOpen,
}: {
  plan: ItineraryPlanVariant
  onOpen: () => void
}) {
  return (
    <button
      type="button"
      className="w-full min-w-[280px] rounded-[8px] border border-blue-100 bg-white px-4 py-4 text-left shadow-sm transition hover:border-blue-200"
      onClick={onOpen}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-lg font-bold leading-7 text-slate-950">{plan.title}</div>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-500">
            <span className="inline-flex items-center gap-1">
              <Clock3 className="h-4 w-4" />
              总时长 <b className="text-slate-700">{formatDuration(plan.total_duration_minutes)}</b>
            </span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="rounded-full bg-emerald-50 px-4 py-2 text-lg font-bold text-emerald-700">
            {formatCost(plan.total_cost)}
          </span>
          <ChevronDown className="h-5 w-5 text-slate-300" />
        </div>
      </div>
    </button>
  )
}

function MockPaymentPanel({ confirmation }: { confirmation: Confirmation }) {
  const applyPaymentCommit = useItineraryStore((s) => s.applyPaymentCommit)
  const [password, setPassword] = useState('')
  const [statusText, setStatusText] = useState('请输入支付密码')
  const [statusTone, setStatusTone] = useState<'neutral' | 'error' | 'success'>('neutral')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const command = confirmation.execution_command ?? null
  const executionId = command?.execution_id ?? confirmation.execution_id ?? ''
  const amount = command?.pricing_summary?.expected_charge_cost
  const planLabel = command?.plan_id ? `行程方案 ${command.plan_id.replace(/^plan_?/i, '').toUpperCase()}` : '已确认行程方案'

  const pushDigit = (digit: string) => {
    if (isSubmitting) return
    setPassword((current) => {
      if (current.length >= 6) return current
      return `${current}${digit}`.slice(0, 6)
    })
    setStatusText('请输入支付密码')
    setStatusTone('neutral')
  }

  const deleteDigit = () => {
    if (isSubmitting) return
    setPassword((current) => current.slice(0, -1))
    setStatusText('请输入支付密码')
    setStatusTone('neutral')
  }

  const submitPayment = async () => {
    if (!executionId || password.length !== 6 || isSubmitting) return
    setIsSubmitting(true)
    setStatusText('正在校验 Mock 支付')
    setStatusTone('neutral')
    try {
      const result = await commitMockPayment(executionId, password)
      if (result.payment_status !== 'paid' || result.commit_status !== 'success') {
        setStatusText(result.message || 'Mock 支付失败')
        setStatusTone('error')
        return
      }
      setStatusText(result.message || '已付款，Mock 执行完成')
      setStatusTone('success')
      applyPaymentCommit(result)
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : 'Mock 支付失败')
      setStatusTone('error')
    } finally {
      setIsSubmitting(false)
    }
  }

  const keypad = ['1', '2', '3', '4', '5', '6', '7', '8', '9']

  return (
    <div className="mb-4 overflow-hidden rounded-[18px] border border-blue-100 bg-gradient-to-b from-white to-blue-50/70 px-4 pb-4 pt-3 text-sm text-slate-950 shadow-[0_14px_42px_rgba(37,99,235,0.14)]">
      <div className="mx-auto mb-4 h-1.5 w-14 rounded-full bg-blue-100" />

      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex min-w-0 gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[14px] bg-blue-600 text-white shadow-sm">
            <CreditCard className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <div className="text-lg font-bold leading-6 text-slate-950">支付订单</div>
            <div className="mt-1 truncate text-xs font-semibold text-slate-500">{planLabel}</div>
          </div>
        </div>
        <div className="shrink-0 pt-1 text-2xl font-black text-blue-600">{amount ? formatCost(amount) : '¥0'}</div>
      </div>

      <div className="space-y-2">
        <div className="flex h-12 items-center justify-between rounded-[8px] border border-amber-100 bg-amber-50/70 px-3">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-[8px] bg-white text-amber-500">
              <Ticket className="h-4 w-4" />
            </span>
            <span className="font-bold text-slate-800">优惠券</span>
            <span className="text-xs font-semibold text-amber-600">演示券可用</span>
          </div>
          <span className="text-sm font-bold text-amber-600">-¥30</span>
        </div>

        <div className="flex h-12 items-center justify-between rounded-[8px] border border-blue-100 bg-blue-50 px-3">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-[8px] bg-white text-blue-600">
              <CreditCard className="h-4 w-4" />
            </span>
            <span className="font-bold text-slate-800">支付方式</span>
            <span className="text-xs font-semibold text-blue-500">Mock 支付</span>
          </div>
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
        </div>
      </div>

      <div className="mt-5 text-center">
        <div className="text-sm font-bold text-slate-800">请输入支付密码</div>
        <div className="mt-3 grid grid-cols-6 gap-2">
          {Array.from({ length: 6 }).map((_, index) => {
            const filled = password.length > index
            const active = password.length === index && password.length < 6
            return (
              <div
                key={index}
                className={[
                  'flex aspect-square min-h-[42px] items-center justify-center rounded-[8px] border bg-white text-xl font-black shadow-sm',
                  active ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-200',
                  filled ? 'text-blue-600' : 'text-transparent',
                ].join(' ')}
              >
                {filled ? '•' : '0'}
              </div>
            )
          })}
        </div>
        <div className="mt-3 flex items-center justify-center gap-1 text-xs font-semibold text-slate-400">
          <ShieldCheck className="h-3.5 w-3.5" />
          演示密码 111111，仅用于本次 Mock 验证
        </div>
        <div
          className={[
            'mt-2 min-h-5 text-xs font-semibold',
            statusTone === 'error' ? 'text-rose-600' : statusTone === 'success' ? 'text-emerald-600' : 'text-blue-500',
          ].join(' ')}
        >
          {statusText}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {keypad.map((digit) => (
          <button
            key={digit}
            type="button"
            className="h-12 rounded-[8px] border border-blue-50 bg-white text-2xl font-black text-blue-950 shadow-sm transition active:scale-[0.98] disabled:text-slate-300"
            disabled={isSubmitting || password.length >= 6}
            onClick={() => pushDigit(digit)}
          >
            {digit}
          </button>
        ))}
        <button
          type="button"
          className="flex h-12 items-center justify-center rounded-[8px] border border-blue-50 bg-white text-blue-700 shadow-sm transition active:scale-[0.98]"
          disabled={isSubmitting}
          onClick={deleteDigit}
          aria-label="删除一位密码"
        >
          <Delete className="h-5 w-5" />
        </button>
        <button
          type="button"
          className="h-12 rounded-[8px] border border-blue-50 bg-white text-2xl font-black text-blue-950 shadow-sm transition active:scale-[0.98] disabled:text-slate-300"
          disabled={isSubmitting || password.length >= 6}
          onClick={() => pushDigit('0')}
        >
          0
        </button>
        <button
          type="button"
          className="h-12 rounded-[8px] bg-blue-600 px-2 text-sm font-black text-white shadow-sm transition active:scale-[0.98] disabled:bg-slate-300"
          disabled={password.length !== 6 || isSubmitting}
          onClick={submitPayment}
        >
          {isSubmitting ? '支付中' : '确认支付'}
        </button>
      </div>
    </div>
  )
}

function PendingPaymentNotice({ confirmation, onOpen }: { confirmation: Confirmation; onOpen: () => void }) {
  const amount = confirmation.execution_command?.pricing_summary?.expected_charge_cost
  return (
    <button
      type="button"
      className="mb-2 flex w-full items-center justify-between gap-3 rounded-[8px] border border-sky-200 bg-sky-50 px-4 py-3 text-left text-sm text-sky-950 shadow-sm"
      onClick={onOpen}
    >
      <span className="flex min-w-0 items-center gap-2 font-bold">
        <CreditCard className="h-4 w-4 shrink-0" />
        <span className="truncate">待支付执行命令</span>
      </span>
      <span className="shrink-0 text-xs font-semibold text-sky-700">
        {amount ? `${formatCost(amount)} · ` : ''}输入 111111
      </span>
    </button>
  )
}

function getStepName(step: ItineraryStep) {
  const item = step.item
  if (item.type === 'commute') return `前往 ${item.commute_to || item.name || '下一站'}`
  return item.display_name || item.parent_name || item.name || '行程项目'
}

function getShareStorageKey(shareId: string) {
  return `closedloop-share-${shareId}`
}

function saveShareSnapshot(plan: ItineraryPlanVariant) {
  const shareId = `share_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  const snapshot = {
    id: shareId,
    title: plan.title,
    total_cost: plan.total_cost,
    total_duration_minutes: plan.total_duration_minutes,
    steps: plan.steps,
    selected_item_ids: plan.selected_item_ids,
    created_at: new Date().toISOString(),
  }
  window.localStorage.setItem(getShareStorageKey(shareId), JSON.stringify(snapshot))
  return `${window.location.origin}/share/${shareId}`
}

function JourneyProgressSheet({ plan, onClose }: { plan: ItineraryPlanVariant; onClose: () => void }) {
  const [stepIndex, setStepIndex] = useState(0)
  const [phase, setPhase] = useState<'heading' | 'arrived'>('heading')
  const [actionText, setActionText] = useState('')
  const currentStep = plan.steps[stepIndex] ?? null
  const isFinished = !currentStep
  const isLastStep = stepIndex >= plan.steps.length - 1
  const isCommute = currentStep?.item.type === 'commute'
  const from = currentStep?.item.commute_from || '当前位置'
  const to = currentStep?.item.commute_to || (currentStep ? getStepName(currentStep) : '目的地')
  const mode = currentStep?.item.commute_recommended_mode || currentStep?.item.commute_mode || 'walking'
  const actionLabel = mode === 'taxi' ? '一键打车' : mode === 'driving' ? '驾车导航' : '步行导航'

  const goNext = () => {
    setActionText('')
    setPhase('heading')
    setStepIndex((value) => value + 1)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-slate-950/50 backdrop-blur-[2px]" onClick={onClose}>
      <div
        className="max-h-[86vh] w-full overflow-y-auto rounded-t-[28px] bg-white px-5 pb-6 pt-4 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <button type="button" className="mx-auto mb-5 block h-6 w-20 rounded-full" onClick={onClose} aria-label="关闭开始行程">
          <span className="mx-auto block h-1.5 w-14 rounded-full bg-slate-300" />
        </button>
        <button
          type="button"
          className="absolute right-5 top-5 flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500"
          onClick={onClose}
          aria-label="关闭"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="pr-12">
          <div className="text-xl font-black text-slate-950">开始行程</div>
          <div className="mt-1 text-sm font-semibold text-blue-600">{plan.title}</div>
        </div>

        {isFinished ? (
          <div className="mt-6 rounded-[12px] border border-emerald-100 bg-emerald-50 px-4 py-5 text-center">
            <Flag className="mx-auto h-8 w-8 text-emerald-500" />
            <div className="mt-3 text-lg font-black text-emerald-700">今日行程完成</div>
            <div className="mt-1 text-sm text-emerald-600">所有站点都已经走完，辛苦啦。</div>
          </div>
        ) : (
          <div className="mt-5 space-y-4">
            <div className="rounded-[12px] border border-blue-100 bg-blue-50 px-4 py-4">
              <div className="text-xs font-bold text-blue-500">
                第 {stepIndex + 1} / {plan.steps.length} 步
              </div>
              <div className="mt-2 text-xl font-black text-slate-950">{getStepName(currentStep)}</div>
              <div className="mt-2 text-sm leading-6 text-slate-600">
                {isCommute
                  ? phase === 'heading'
                    ? `准备从 ${from} 前往 ${to}`
                    : `已到达 ${to}`
                  : `建议体验 ${Math.round(Number(currentStep.duration_minutes || 0))} 分钟`}
              </div>
              {currentStep.start_time || currentStep.end_time ? (
                <div className="mt-2 text-xs font-semibold text-blue-600">
                  {currentStep.start_time || '--:--'} - {currentStep.end_time || '--:--'}
                </div>
              ) : null}
            </div>

            {isCommute ? (
              <div className="rounded-[12px] border border-slate-200 bg-white px-4 py-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-black text-slate-900">
                  <MapPinned className="h-4 w-4 text-blue-500" />
                  转场助手
                </div>
                <button
                  type="button"
                  className="h-11 w-full rounded-[8px] bg-blue-600 text-sm font-black text-white"
                  onClick={() =>
                    setActionText(
                      mode === 'taxi' ? '已生成 Mock 打车单，司机预计 3 分钟后到达' : `已打开 Mock 导航：从 ${from} 前往 ${to}`,
                    )
                  }
                >
                  {actionLabel}
                </button>
                {actionText ? (
                  <div className="mt-3 rounded-[8px] bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700">
                    {actionText}
                  </div>
                ) : null}
              </div>
            ) : null}

            <button
              type="button"
              className="h-12 w-full rounded-[8px] bg-blue-600 text-base font-black text-white shadow-lg shadow-blue-100"
              onClick={() => {
                if (isCommute && phase === 'heading') {
                  setPhase('arrived')
                  return
                }
                if (isLastStep) {
                  setStepIndex(plan.steps.length)
                  return
                }
                goNext()
              }}
            >
              {isCommute && phase === 'heading' ? '已到达' : isLastStep ? '完成行程' : '完成本项，下一站'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

void JourneyProgressSheet

export function PlanPanel({ itinerary, confirmation, errorMessage }: Props) {
  const invokeStatus = useItineraryStore((s) => s.invokeStatus)
  const [selectedStep, setSelectedStep] = useState<ItineraryStep | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null)
  const [journeyPlan, setJourneyPlan] = useState<ItineraryPlanVariant | null>(null)
  const [shareStatus, setShareStatus] = useState('')
  const plans = Array.isArray(itinerary?.plans) ? itinerary.plans : []
  const hasPlans = plans.length > 0
  const selectedPlan = plans.find((plan) => plan.plan_id === selectedPlanId) ?? null
  const isPendingPayment = confirmation?.status === 'pending_payment'
  const executedPlanId = confirmation?.execution_command?.plan_id
  const actionPlan = plans.find((plan) => plan.plan_id === executedPlanId) ?? selectedPlan ?? plans[0] ?? null

  const summaryText = useMemo(() => {
    if (hasPlans) return `已生成 ${plans.length} 套可执行方案`
    if (confirmation) return `当前确认状态：${confirmation.status}`
    if (errorMessage) return errorMessage
    return '方案生成完成后会展示在这里。'
  }, [confirmation, errorMessage, hasPlans, plans.length])

  const isFixupFinished = confirmation?.status === 'executed' || confirmation?.status === 'failed'
  const fixupPayload = isFixupFinished ? null : (confirmation as any)?.fixup ?? null
  const backupCandidates = Array.isArray(fixupPayload?.backup_candidates)
    ? (fixupPayload.backup_candidates as any[])
    : []
  const topCandidates = backupCandidates.slice(0, 2)

  const executionSummary =
    (confirmation as any)?.execution_summary ?? (confirmation as any)?.executionSummary ?? null
  const replacements = Array.isArray(executionSummary?.replacements) ? executionSummary.replacements : []
  const failures = Array.isArray(executionSummary?.failures) ? executionSummary.failures : []

  const collapsePanel = () => {
    setSelectedStep(null)
    setSelectedPlanId(null)
    setIsExpanded(false)
  }

  const openPanel = () => {
    setSelectedStep(null)
    setSelectedPlanId(null)
    setIsExpanded(true)
  }

  const sharePlan = async () => {
    if (!actionPlan) return
    const shareUrl = saveShareSnapshot(actionPlan)
    try {
      await navigator.clipboard.writeText(shareUrl)
      setShareStatus('分享链接已复制')
    } catch {
      setShareStatus(shareUrl)
    }
  }

  if (!itinerary && !confirmation && !errorMessage) {
    return (
      <div className="px-4 pb-4">
        <div className="rounded-[8px] border border-slate-200 bg-white px-4 py-5 text-sm text-slate-500 shadow-sm">
          方案生成完成后会展示在这里。
        </div>
      </div>
    )
  }

  if (!itinerary && errorMessage) {
    return (
      <div className="px-4 pb-4">
        <div className="rounded-[8px] border border-rose-200 bg-rose-50 px-4 py-5 text-sm text-rose-600 shadow-sm">
          {errorMessage}
        </div>
      </div>
    )
  }

  if (hasPlans && !isExpanded) {
    return (
      <div className="px-4 pb-2">
        {isPendingPayment && confirmation ? (
          <PendingPaymentNotice confirmation={confirmation} onOpen={openPanel} />
        ) : null}
        <button
          type="button"
          className="mx-auto flex h-9 w-32 items-center justify-center rounded-t-[22px] border border-b-0 border-slate-200 bg-white shadow-[0_-8px_28px_rgba(15,23,42,0.10)]"
          aria-label="展开推荐方案"
          aria-expanded={false}
          onClick={openPanel}
        >
          <span className="h-1.5 w-14 rounded-full bg-slate-300" />
        </button>
      </div>
    )
  }

  return (
    <div className="px-0 pb-4">
      <section className="rounded-t-[28px] border border-slate-200 bg-white/95 px-5 pb-5 pt-4 shadow-[0_-18px_60px_rgba(15,23,42,0.12)] backdrop-blur">
        <button
          type="button"
          className="mx-auto mb-5 block h-6 w-20 rounded-full"
          aria-label="收起推荐方案"
          aria-expanded={true}
          onClick={collapsePanel}
        >
          <span className="mx-auto block h-1.5 w-14 rounded-full bg-slate-300" />
        </button>

        {confirmation?.status === 'needs_fixup' &&
        invokeStatus !== 'running' &&
        backupCandidates.length > 0 ? (
          <div className="mb-4 rounded-[8px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <div className="font-semibold">需要你确认</div>
            <div className="mt-1 text-xs text-amber-800">
              执行遇到备选替换。请在输入框回复：选 1 / 选 2 / 搜索关键词。
            </div>
            <div className="mt-3 space-y-2 text-xs text-amber-900">
              {topCandidates.map((candidate, index) => (
                <div key={String(candidate?.id ?? index)} className="rounded-[8px] bg-white/70 px-3 py-2">
                  <div className="font-semibold">
                    候选 {index + 1}：{String(candidate?.name ?? candidate?.id ?? '')}
                  </div>
                  {candidate?.violation_reason ? (
                    <div className="mt-1 text-amber-800">原因：{String(candidate.violation_reason)}</div>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {isPendingPayment ? (
          <MockPaymentPanel confirmation={confirmation} />
        ) : null}

        {confirmation?.status === 'executed' && actionPlan ? (
          <div className="mb-4 rounded-[8px] border border-blue-100 bg-blue-50 px-4 py-3">
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                className="flex h-11 items-center justify-center gap-2 rounded-[8px] bg-blue-600 text-sm font-black text-white shadow-sm"
                onClick={() => setJourneyPlan(actionPlan)}
              >
                <Play className="h-4 w-4" />
                开始执行
              </button>
              <button
                type="button"
                className="flex h-11 items-center justify-center gap-2 rounded-[8px] border border-blue-200 bg-white text-sm font-black text-blue-600"
                onClick={sharePlan}
              >
                <Share2 className="h-4 w-4" />
                分享行程
              </button>
            </div>
            {shareStatus ? (
              <div className="mt-2 flex items-center gap-1 text-xs font-semibold text-blue-600">
                <Copy className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{shareStatus}</span>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-xl font-bold text-slate-950">推荐方案</h2>
            <p className="mt-1 text-sm text-slate-500">{summaryText}</p>
          </div>
        </div>

        <div className="mt-5 max-h-[62vh] overflow-y-auto pr-1">
          {!hasPlans ? (
            <div className="rounded-[8px] bg-slate-50 px-4 py-3 text-sm text-slate-500">
              当前条件下暂时没有生成出合适方案，可以继续调整需求后重试。
            </div>
          ) : selectedPlan ? (
            <div>
              <button
                type="button"
                className="mb-4 inline-flex items-center gap-1 rounded-full bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500"
                onClick={() => {
                  setSelectedStep(null)
                  setSelectedPlanId(null)
                }}
              >
                <ChevronLeft className="h-4 w-4" />
                返回方案列表
              </button>
              <PlanCard
                plan={selectedPlan}
                copywriting={confirmation?.plans?.[selectedPlan.plan_id as keyof ThreePlansCopywriting]}
                selectedStep={selectedStep}
                onOpenStep={setSelectedStep}
                onCloseStep={() => setSelectedStep(null)}
                onCollapsePanel={collapsePanel}
              />
            </div>
          ) : (
            <div className="flex gap-3 overflow-x-auto pb-1">
              {plans.map((plan) => (
                <div key={plan.plan_id} className="w-[84%] max-w-[360px] shrink-0">
                  <PlanSummaryCard
                    plan={plan}
                    onOpen={() => {
                      setSelectedStep(null)
                      setSelectedPlanId(plan.plan_id)
                    }}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {confirmation ? (
          <div className="mt-4 rounded-[8px] border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            当前确认状态：{confirmation.status}
            {confirmation.reason ? ` · ${confirmation.reason}` : ''}
          </div>
        ) : null}

        {confirmation?.status === 'executed' && executionSummary ? (
          <div className="mt-4 rounded-[8px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            <div className="font-semibold text-slate-900">执行结果</div>
            <div className="mt-2 space-y-2">
              <div className="text-xs text-slate-500">已替换 {replacements.length} 项</div>
              {replacements.length > 0 ? (
                <div className="space-y-1">
                  {replacements.map((item: any, idx: number) => (
                    <div key={`${item.original_id ?? idx}`} className="text-sm">
                      {(item.original_name as string) || (item.original_id as string) || '原项'} -&gt;{' '}
                      {(item.new_item_name as string) || (item.new_item_id as string) || '备选项'}
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
                      {(item.item_name as string) || (item.item_id as string) || '预约失败'}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500">无失败项</div>
              )}
            </div>
          </div>
        ) : null}
      </section>
      {journeyPlan ? (
        <div className="fixed inset-0 z-50 flex flex-col bg-[#EEF2F7]">
          <JourneyView plan={journeyPlan} mode="active" title="开始执行" fitContainer showHeader={true} onClose={() => setJourneyPlan(null)} />
        </div>
      ) : null}
    </div>
  )
}

import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, Clock3, Wallet, Footprints, ChevronRight, Pencil } from 'lucide-react'
import { useItineraryStore } from '../features/itinerary/store/useItineraryStore'
import type {
  ItineraryItemType,
  ItineraryPlanVariant,
  PlanCopywriting,
} from '../features/itinerary/model/types'
import {
  commuteModeLabel,
  resolveItemSubtitle,
  resolveItemTitle,
} from '../features/itinerary/model/display'
import {
  formatDurationMinutes,
  formatMoney,
  formatMoneyExact,
  minutesToTime,
  parseTimeToMinutes,
} from '../shared/lib/format'
import Skeleton from '../shared/ui/Skeleton'
import BottomSheet from '../shared/ui/BottomSheet'
import PrimaryButton from '../shared/ui/PrimaryButton'

type CommuteMode = 'walking' | 'taxi' | 'driving'

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

function estimateWalkPressure(plan: ItineraryPlanVariant): '低' | '中' | '高' {
  const commuteMinutes = plan.steps
    .filter((s) => s.item.type === 'commute')
    .reduce((acc, s) => acc + (Number.isFinite(s.duration_minutes) ? s.duration_minutes : 0), 0)

  if (commuteMinutes <= 25) return '低'
  if (commuteMinutes <= 50) return '中'
  return '高'
}

export default function PlanDetailPage() {
  const navigate = useNavigate()
  const { planId } = useParams()
  const state = useItineraryStore((s) => s.state)
  const plan = state?.itinerary?.plans?.find((p) => p.plan_id === planId) ?? null
  const timePeriod = state?.constraints?.time_period ?? ''
  const updateCommuteMode = useItineraryStore((s) => s.updateCommuteMode)
  const copywriting =
    (state?.confirmation?.plans as Record<string, PlanCopywriting> | undefined)?.[planId ?? ''] ??
    null

  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [pendingCommuteMode, setPendingCommuteMode] = useState<CommuteMode | null>(null)
  const [startMinutesOverride, setStartMinutesOverride] = useState<number | null>(null)
  const [endMinutesOverride, setEndMinutesOverride] = useState<number | null>(null)
  const [startTimeSheetOpen, setStartTimeSheetOpen] = useState(false)
  const [pendingStartMinutes, setPendingStartMinutes] = useState(0)
  const [endTimeSheetOpen, setEndTimeSheetOpen] = useState(false)
  const [pendingEndMinutes, setPendingEndMinutes] = useState(0)

  const startMinutes = useMemo(() => {
    const trimmed = timePeriod.trim()
    const m = /^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/.exec(trimmed)
    if (m) return parseTimeToMinutes(m[1])
    if (/^\d{1,2}:\d{2}$/.test(trimmed)) return parseTimeToMinutes(trimmed)
    return null
  }, [timePeriod])

  const totalPlanMinutes = useMemo(() => {
    if (!plan) return 0
    return plan.steps.reduce(
      (acc, s) => acc + (Number.isFinite(s.duration_minutes) ? s.duration_minutes : 0),
      0,
    )
  }, [plan])

  const effectiveStartMinutes = useMemo(() => {
    if (startMinutesOverride != null) return startMinutesOverride
    if (endMinutesOverride != null && plan) {
      const derived = endMinutesOverride - totalPlanMinutes
      return ((derived % (24 * 60)) + 24 * 60) % (24 * 60)
    }
    return startMinutes ?? 13 * 60
  }, [endMinutesOverride, plan, startMinutes, startMinutesOverride, totalPlanMinutes])

  const timeline = useMemo(() => {
    if (!plan) return []
    let cursor = effectiveStartMinutes
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
  }, [effectiveStartMinutes, plan])

  const selectedStep = selectedIdx == null ? null : timeline[selectedIdx] ?? null
  const selectedStepTitle = selectedStep ? resolveItemTitle(selectedStep.item) : ''
  const selectedStepSubtitle = selectedStep
    ? resolveItemSubtitle(selectedStep.item, { note: selectedStep.note, fallback: '暂无补充信息' })
    : ''
  const pendingOption =
    selectedStep?.item.type === 'commute' && pendingCommuteMode
      ? (selectedStep.item.commute_options ?? []).find((o) => o.mode === pendingCommuteMode) ?? null
      : null

  if (!plan) {
    return (
      <main className="min-h-screen bg-[#F7F8FC] px-5 pt-14 pb-40">
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

  const walkPressure = estimateWalkPressure(plan)

  return (
    <>
      <main className="min-h-screen bg-[#F7F8FC] px-5 pt-10 pb-40">
        <div className="mx-auto max-w-[430px]">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => navigate(-1)}
              className="h-10 w-10 rounded-full bg-white border border-slate-100 flex items-center justify-center"
              aria-label="返回"
            >
              <ChevronLeft className="h-5 w-5 text-slate-700" />
            </button>
            <div>
              <div className="text-xl font-semibold text-slate-900">方案详情</div>
              <div className="text-xs text-slate-500 mt-0.5">
                {copywriting?.plan_name?.trim()
                  ? copywriting.plan_name
                  : plan.title?.trim()
                    ? plan.title
                    : plan.plan_id}
              </div>
            </div>
          </div>

          <div className="mt-5 rounded-3xl bg-white p-4 shadow-sm border border-slate-100">
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-2xl bg-slate-50 p-3">
                <div className="text-xs text-slate-500 inline-flex items-center gap-1">
                  <Clock3 className="h-3.5 w-3.5" />
                  总时长
                </div>
                <div className="mt-1 text-sm font-semibold text-slate-900">
                  {formatDurationMinutes(plan.total_duration_minutes)}
                </div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-3">
                <div className="text-xs text-slate-500 inline-flex items-center gap-1">
                  <Wallet className="h-3.5 w-3.5" />
                  预计花费
                </div>
                <div className="mt-1 text-sm font-semibold text-slate-900">
                  {formatMoney(plan.total_cost)}
                </div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-3">
                <div className="text-xs text-slate-500 inline-flex items-center gap-1">
                  <Footprints className="h-3.5 w-3.5" />
                  步行压力
                </div>
                <div className="mt-1 text-sm font-semibold text-emerald-700">
                  {walkPressure}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 rounded-3xl bg-white p-4 shadow-sm border border-slate-100">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-slate-900">行程安排</div>
              <div className="text-xs text-slate-500">共 {timeline.length} 个行程</div>
            </div>

            <div className="mt-4 space-y-4">
              {timeline.map((s, idx) => {
                const isGift = s.item.type === 'gift_shop'
                const meta =
                  s.item.type === 'commute'
                    ? { ...getTypeMeta(s.item.type), icon: commuteModeIcon(s.item.commute_mode) }
                    : getTypeMeta(s.item.type)
                const giftDesc =
                  s.note?.trim()
                    ? s.note
                    : s.item.type !== 'commute' && s.item.intro?.trim()
                      ? s.item.intro
                      : '准备一个小惊喜'
                return (
                  <div key={`${plan.plan_id}_${idx}`} className="flex gap-3">
                    <div className="w-12 flex flex-col items-center">
                      {isGift ? (
                        <div className="h-6" />
                      ) : idx === timeline.length - 1 &&
                        s.item.type === 'commute' && (s.item.commute_to ?? '').includes('家') ? (
                        <button
                          type="button"
                          aria-label="调整到家时间"
                          onClick={() => {
                            const end = (effectiveStartMinutes + totalPlanMinutes) % (24 * 60)
                            setPendingEndMinutes(end)
                            setEndTimeSheetOpen(true)
                          }}
                          className={[
                            'inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full border shadow-sm',
                            endTimeSheetOpen
                              ? 'text-blue-700 border-blue-300 bg-blue-100'
                              : 'text-blue-700 border-blue-200 bg-blue-50 hover:bg-blue-100',
                          ].join(' ')}
                        >
                          <span>{s.end_time}</span>
                          <Pencil className="h-3 w-3" />
                        </button>
                      ) : idx === 0 ? (
                        <button
                          type="button"
                          aria-label="调整初始时间"
                          onClick={() => {
                            setPendingStartMinutes(effectiveStartMinutes)
                            setStartTimeSheetOpen(true)
                          }}
                          className={[
                            'inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full border shadow-sm',
                            startTimeSheetOpen
                              ? 'text-blue-700 border-blue-300 bg-blue-100'
                              : 'text-blue-700 border-blue-200 bg-blue-50 hover:bg-blue-100',
                          ].join(' ')}
                        >
                          <span>{s.start_time}</span>
                          <Pencil className="h-3 w-3" />
                        </button>
                      ) : (
                        <div className="text-xs text-slate-500">{s.start_time}</div>
                      )}
                      <div className="mt-2 h-full w-px bg-slate-200" />
                    </div>

                    <button
                      type="button"
                      onClick={() => setSelectedIdx(idx)}
                      className={
                        isGift
                          ? 'flex-1 rounded-2xl border border-violet-100 bg-violet-50 p-3 text-left hover:border-violet-200'
                          : 'flex-1 rounded-2xl border border-slate-100 bg-slate-50 p-3 text-left hover:border-slate-200'
                      }
                    >
                      {isGift ? (
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-lg leading-none">{meta.icon}</span>
                              <div className="text-sm font-semibold text-slate-900">
                                {resolveItemTitle(s.item)}
                              </div>
                            </div>
                            <div className="mt-1 text-xs text-slate-600">{giftDesc}</div>
                            <div className="mt-2 text-[11px] text-violet-700">
                              预计 {s.end_time} 前完成
                            </div>
                          </div>
                          <div className="inline-flex items-center gap-2">
                            <span className="rounded-full bg-white/70 border border-violet-200 px-2 py-1 text-[11px] font-semibold text-violet-700">
                              {formatMoney(s.item.cost ?? 0)}
                            </span>
                            <ChevronRight className="h-4 w-4 text-violet-300" />
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-lg leading-none">{meta.icon}</span>
                              <div className="text-sm font-semibold text-slate-900">
                                {resolveItemTitle(s.item)}
                              </div>
                            </div>
                            <div className="mt-1 text-xs text-slate-500">
                              {s.item.type === 'commute'
                                ? resolveItemSubtitle(s.item, { note: s.note })
                                : resolveItemSubtitle(s.item, { note: s.note, fallback: '详情生成中…' })}
                            </div>
                            {s.item.type === 'commute' ? (
                              <div className="mt-1 text-[11px] text-slate-400">
                                预计 {s.end_time}{' '}
                                {(s.item.commute_to ?? '').includes('家') ? '到家' : '到达'}
                              </div>
                            ) : null}
                          </div>
                          <div className="inline-flex items-center gap-2">
                            <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${meta.pill}`}>
                              {Number.isFinite(s.duration_minutes) ? `${s.duration_minutes}分钟` : '--'}
                            </span>
                            <span className="rounded-full bg-white border border-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-700">
                              {formatMoney(s.item.cost ?? 0)}
                            </span>
                            <ChevronRight className="h-4 w-4 text-slate-300" />
                          </div>
                        </div>
                      )}
                    </button>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="mt-5 rounded-3xl bg-white p-4 shadow-sm border border-slate-100">
            <div className="text-sm font-semibold text-slate-900">
              为什么推荐这套
            </div>
            <div className="mt-3 space-y-2">
              {(copywriting?.pros_cons ?? []).length ? (
                (copywriting?.pros_cons ?? []).map((t) => (
                  <div key={t} className="text-sm text-slate-700">
                    {t}
                  </div>
                ))
              ) : (
                <>
                  <Skeleton className="h-4 w-64" />
                  <Skeleton className="h-4 w-56" />
                  <Skeleton className="h-4 w-44" />
                </>
              )}
            </div>
            {copywriting?.ai_reminder?.trim() ? (
              <div className="mt-3 whitespace-pre-line text-xs text-slate-500">
                {copywriting.ai_reminder}
              </div>
            ) : (
              <div className="mt-3 text-xs text-slate-400">生成中…</div>
            )}
          </div>
        </div>
      </main>
      <div className="fixed bottom-0 left-0 right-0 z-30 mx-auto max-w-[430px] rounded-t-[28px] bg-white/90 px-5 pb-6 pt-4 shadow-2xl backdrop-blur border-t border-slate-100">
        <PrimaryButton label="选择这套方案" onClick={() => navigate(`/app/executing/${plan.plan_id}`)} />
      </div>

      <BottomSheet
        open={selectedStep != null}
        title={selectedStepTitle}
        onClose={() => setSelectedIdx(null)}
      >
        {selectedStep ? (
          <div className="space-y-4">
            <div className="rounded-2xl bg-slate-50 border border-slate-100 p-3">
              <div className="text-xs text-slate-500">地址 / 位置</div>
              <div className="mt-1 text-sm text-slate-900">
                {selectedStep.item.location || '未知'}
              </div>
              <div className="mt-2 flex items-center gap-4 text-xs text-slate-600">
                <div>
                  距离 <span className="font-semibold">{selectedStep.item.distance_km?.toFixed?.(1) ?? selectedStep.item.distance_km}</span> km
                </div>
                <div>
                  费用{' '}
                  <span className="font-semibold">
                    {selectedStep.item.type === 'commute'
                      ? formatMoneyExact(selectedStep.item.cost ?? 0)
                      : formatMoney(selectedStep.item.cost ?? 0)}
                  </span>
                </div>
              </div>
            </div>

            {selectedStep.item.type === 'gift_shop' ? (
              <div className="rounded-2xl bg-white border border-violet-100 p-3">
                <div className="text-sm font-semibold text-slate-900">配送信息</div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-xl bg-violet-50 border border-violet-100 p-2">
                    <div className="text-[11px] text-violet-700">礼物价格</div>
                    <div className="mt-1 font-semibold text-slate-900">
                      {formatMoneyExact(selectedStep.item.gift_price ?? (selectedStep.item.cost ?? 0))}
                    </div>
                  </div>
                  <div className="rounded-xl bg-violet-50 border border-violet-100 p-2">
                    <div className="text-[11px] text-violet-700">配送费</div>
                    <div className="mt-1 font-semibold text-slate-900">
                      {formatMoneyExact(selectedStep.item.delivery_fee ?? 0)}
                    </div>
                  </div>
                  <div className="rounded-xl bg-violet-50 border border-violet-100 p-2">
                    <div className="text-[11px] text-violet-700">配送距离</div>
                    <div className="mt-1 font-semibold text-slate-900">
                      {(selectedStep.item.delivery_distance_km ?? selectedStep.item.distance_km)?.toFixed?.(1) ??
                        (selectedStep.item.delivery_distance_km ?? selectedStep.item.distance_km)}{' '}
                      km
                    </div>
                  </div>
                </div>
                <div className="mt-3 text-[11px] text-slate-500">
                  配送费规则：起步 3 元 + 2 元/公里，封顶 15 元（范围内可送达）。
                </div>
              </div>
            ) : null}

            {selectedStep.item.type === 'commute' ? (
              <div className="rounded-2xl bg-white border border-slate-100 p-3">
                <div className="text-sm font-semibold text-slate-900">通勤信息</div>
                <div className="mt-2 text-xs text-slate-600">
                  {selectedStep.item.commute_from ?? '出发点'} → {selectedStep.item.commute_to ?? '目的地'}
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {(selectedStep.item.commute_options ?? []).map((o) => {
                    const active = (selectedStep.item.commute_mode ?? null) === o.mode
                    return (
                      <button
                        key={o.mode}
                        type="button"
                        onClick={() => setPendingCommuteMode(o.mode)}
                        className={[
                          'rounded-xl border px-3 py-2 text-left',
                          active ? 'border-blue-300 bg-blue-50' : 'border-slate-200 bg-white',
                        ].join(' ')}
                      >
                        <div className="text-xs font-semibold text-slate-900">
                          {commuteModeIcon(o.mode)} {commuteModeLabel(o.mode)}
                        </div>
                        <div className="mt-1 text-[11px] text-slate-600">
                          {o.time_minutes} 分钟 · {formatMoneyExact(o.cost)}
                        </div>
                      </button>
                    )
                  })}
                </div>

                {pendingCommuteMode && pendingOption ? (
                  <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 p-3">
                    <div className="text-sm font-semibold text-slate-900">
                      更换为「{commuteModeLabel(pendingCommuteMode)}」？
                    </div>
                    <div className="mt-1 text-xs text-slate-600">
                      {pendingOption.time_minutes} 分钟 · {formatMoneyExact(pendingOption.cost)}
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          updateCommuteMode(plan.plan_id, selectedStep.item.id, pendingCommuteMode)
                          setPendingCommuteMode(null)
                        }}
                        className="h-11 rounded-xl bg-slate-900 text-white text-sm font-semibold"
                      >
                        更换方式
                      </button>
                      <button
                        type="button"
                        onClick={() => setPendingCommuteMode(null)}
                        className="h-11 rounded-xl bg-white border border-slate-200 text-slate-700 text-sm font-semibold"
                      >
                        取消
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 text-[11px] text-slate-400">
                    点选交通方式后会弹出确认框。
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-2xl bg-white border border-slate-100 p-3">
                {selectedStepSubtitle && selectedStepSubtitle !== selectedStepTitle ? (
                  <>
                    <div className="text-sm font-semibold text-slate-900">套餐 / 票种</div>
                    <div className="mt-2 text-sm text-slate-700 whitespace-pre-wrap">
                      {selectedStepSubtitle}
                    </div>
                    <div className="mt-3 border-t border-slate-100" />
                  </>
                ) : null}
                <div className="text-sm font-semibold text-slate-900">介绍</div>
                <div className="mt-2 text-sm text-slate-800 whitespace-pre-wrap">
                  {selectedStep.item.intro?.trim() ? selectedStep.item.intro : '暂无介绍'}
                </div>
                <div className="mt-3 text-xs font-semibold text-slate-900">特色</div>
                <div className="mt-1 text-xs text-slate-600 whitespace-pre-wrap">
                  {selectedStep.item.features?.trim() ? selectedStep.item.features : '暂无特色信息'}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </BottomSheet>

      <BottomSheet
        open={startTimeSheetOpen}
        title="调整初始时间"
        onClose={() => setStartTimeSheetOpen(false)}
      >
        <div className="space-y-4">
          <div className="rounded-2xl bg-slate-50 border border-slate-100 p-4">
            <div className="flex items-center justify-center gap-3">
              <div className="text-sm text-slate-500">今天</div>
              <select
                className="h-12 rounded-xl border border-slate-200 bg-white px-3 text-lg font-semibold text-slate-900"
                value={Math.floor(pendingStartMinutes / 60) % 24}
                onChange={(e) => {
                  const h = Number(e.target.value)
                  const m = pendingStartMinutes % 60
                  setPendingStartMinutes(h * 60 + m)
                }}
                aria-label="小时"
              >
                {Array.from({ length: 24 }).map((_, h) => (
                  <option key={h} value={h}>
                    {String(h).padStart(2, '0')}
                  </option>
                ))}
              </select>
              <div className="text-lg font-semibold text-slate-900">:</div>
              <select
                className="h-12 rounded-xl border border-slate-200 bg-white px-3 text-lg font-semibold text-slate-900"
                value={pendingStartMinutes % 60}
                onChange={(e) => {
                  const m = Number(e.target.value)
                  const h = Math.floor(pendingStartMinutes / 60) % 24
                  setPendingStartMinutes(h * 60 + m)
                }}
                aria-label="分钟"
              >
                {Array.from({ length: 60 }).map((_, m) => (
                  <option key={m} value={m}>
                    {String(m).padStart(2, '0')}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-2">
            {[
              { label: '-15 分钟', delta: -15 },
              { label: '-1 小时', delta: -60 },
              { label: '+15 分钟', delta: 15 },
              { label: '+1 小时', delta: 60 },
            ].map((x) => (
              <button
                key={x.label}
                type="button"
                onClick={() => {
                  const next = (pendingStartMinutes + x.delta) % (24 * 60)
                  setPendingStartMinutes(next)
                }}
                className="h-11 rounded-full bg-slate-100 text-sm text-slate-700"
              >
                {x.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => {
              setStartMinutesOverride(null)
              setPendingStartMinutes(startMinutes ?? 13 * 60)
            }}
            className="h-11 w-full rounded-full bg-slate-100 text-sm font-semibold text-slate-700"
          >
            恢复
          </button>

          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setStartTimeSheetOpen(false)}
              className="h-12 rounded-full bg-slate-100 text-sm font-semibold text-slate-700"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => {
                setStartMinutesOverride(pendingStartMinutes)
                setEndMinutesOverride(null)
                setStartTimeSheetOpen(false)
              }}
              className="h-12 rounded-full bg-slate-900 text-sm font-semibold text-white"
            >
              确认
            </button>
          </div>
        </div>
      </BottomSheet>

      <BottomSheet open={endTimeSheetOpen} title="调整到家时间" onClose={() => setEndTimeSheetOpen(false)}>
        <div className="space-y-4">
          <div className="rounded-2xl bg-slate-50 border border-slate-100 p-4">
            <div className="flex items-center justify-center gap-3">
              <div className="text-sm text-slate-500">今天</div>
              <select
                className="h-12 rounded-xl border border-slate-200 bg-white px-3 text-lg font-semibold text-slate-900"
                value={Math.floor(pendingEndMinutes / 60) % 24}
                onChange={(e) => {
                  const h = Number(e.target.value)
                  const m = pendingEndMinutes % 60
                  setPendingEndMinutes(h * 60 + m)
                }}
                aria-label="小时"
              >
                {Array.from({ length: 24 }).map((_, h) => (
                  <option key={h} value={h}>
                    {String(h).padStart(2, '0')}
                  </option>
                ))}
              </select>
              <div className="text-lg font-semibold text-slate-900">:</div>
              <select
                className="h-12 rounded-xl border border-slate-200 bg-white px-3 text-lg font-semibold text-slate-900"
                value={pendingEndMinutes % 60}
                onChange={(e) => {
                  const m = Number(e.target.value)
                  const h = Math.floor(pendingEndMinutes / 60) % 24
                  setPendingEndMinutes(h * 60 + m)
                }}
                aria-label="分钟"
              >
                {Array.from({ length: 60 }).map((_, m) => (
                  <option key={m} value={m}>
                    {String(m).padStart(2, '0')}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-2">
            {[
              { label: '-15 分钟', delta: -15 },
              { label: '-1 小时', delta: -60 },
              { label: '+15 分钟', delta: 15 },
              { label: '+1 小时', delta: 60 },
            ].map((x) => (
              <button
                key={x.label}
                type="button"
                onClick={() => {
                  const next = (pendingEndMinutes + x.delta) % (24 * 60)
                  setPendingEndMinutes(next)
                }}
                className="h-11 rounded-full bg-slate-100 text-sm text-slate-700"
              >
                {x.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => {
              setEndMinutesOverride(null)
              setPendingEndMinutes((effectiveStartMinutes + totalPlanMinutes) % (24 * 60))
            }}
            className="h-11 w-full rounded-full bg-slate-100 text-sm font-semibold text-slate-700"
          >
            恢复
          </button>

          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setEndTimeSheetOpen(false)}
              className="h-12 rounded-full bg-slate-100 text-sm font-semibold text-slate-700"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => {
                setEndMinutesOverride(pendingEndMinutes)
                setStartMinutesOverride(null)
                setEndTimeSheetOpen(false)
              }}
              className="h-12 rounded-full bg-slate-900 text-sm font-semibold text-white"
            >
              确认
            </button>
          </div>
        </div>
      </BottomSheet>
    </>
  )
}

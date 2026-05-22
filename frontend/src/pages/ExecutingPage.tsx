import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, HelpCircle, CheckCircle2 } from 'lucide-react'
import { useItineraryStore } from '../features/itinerary/store/useItineraryStore'
import type { ExecuteEvent, ExecuteRequest, ItineraryPlanVariant } from '../features/itinerary/model/types'
import { resolveItemSubtitle, resolveItemTitle } from '../features/itinerary/model/display'
import { executeStart } from '../features/itinerary/api/executeStart'
import { minutesToTime, parseTimeToMinutes } from '../shared/lib/format'
import { buildApiUrl } from '../shared/lib/url'

type TimelineStep = {
  start_time: string
  end_time: string
} & ItineraryPlanVariant['steps'][number]

type ExecPhase = 'waiting' | 'checking' | 'reserving' | 'done'

type ExecNode = {
  id: string
  type: 'commute' | 'restaurant' | 'activity' | 'gift_shop'
  title: string
  sub_title?: string
  start_time: string
  end_time: string
  commute_mode?: 'walking' | 'taxi' | 'driving' | null
}

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

function pickTaxiCommuteNode(timeline: TimelineStep[]): TimelineStep | null {
  const commutes = timeline.filter((s) => s.item.type === 'commute')
  if (!commutes.length) return null
  const preferred =
    commutes.find((s) => s.item.commute_from === '家' && s.item.commute_mode === 'taxi') ??
    commutes.find((s) => s.item.commute_mode === 'taxi') ??
    null
  return preferred
}

export default function ExecutingPage() {
  const navigate = useNavigate()
  const { planId } = useParams()
  const state = useItineraryStore((s) => s.state)
  const timePeriod = state?.constraints?.time_period ?? ''
  const plan = state?.itinerary?.plans?.find((p) => p.plan_id === planId) ?? null

  const timeline = useMemo(() => {
    if (!plan) return []
    return calcTimeline(plan, timePeriod)
  }, [plan, timePeriod])

  const execNodes = useMemo<ExecNode[]>(() => {
    if (!timeline.length) return []

    const nodes: ExecNode[] = []
    const taxiCommute = pickTaxiCommuteNode(timeline)
    if (taxiCommute) {
      const title = resolveItemTitle(taxiCommute.item).replaceAll(' -> ', ' → ')
      nodes.push({
        id: taxiCommute.item.id,
        type: 'commute',
        title: `预定出租车：${title}`,
        sub_title: resolveItemSubtitle(taxiCommute.item, { note: taxiCommute.note }),
        start_time: taxiCommute.start_time,
        end_time: taxiCommute.end_time,
        commute_mode: taxiCommute.item.commute_mode ?? null,
      })
    }

    for (const s of timeline) {
      if (s.item.type === 'commute') continue
      nodes.push({
        id: s.item.id,
        type: s.item.type,
        title: resolveItemTitle(s.item),
        sub_title: resolveItemSubtitle(s.item, { note: s.note }),
        start_time: s.start_time,
        end_time: s.end_time,
      })
    }

    return nodes
  }, [timeline])

  const [execStatus, setExecStatus] = useState<'idle' | 'running' | 'paused' | 'done' | 'error'>('idle')
  const [statusText, setStatusText] = useState('让我们开始今天的行程吧')
  const [phases, setPhases] = useState<Record<string, ExecPhase>>({})
  const [currentItemId, setCurrentItemId] = useState<string | null>(null)
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({})

  const esRef = useRef<EventSource | null>(null)
  const executionIdRef = useRef<string | null>(null)
  const startedRef = useRef(false)

  const total = execNodes.length
  const doneCount = useMemo(
    () => execNodes.filter((n) => phases[n.id] === 'done').length,
    [execNodes, phases],
  )
  const progress = useMemo(() => {
    if (!execNodes.length) return 0
    const totalProgress = execNodes.reduce((acc, n) => {
      const p = phases[n.id] ?? 'waiting'
      if (p === 'done') return acc + 1
      if (p === 'reserving') return acc + 0.5
      return acc
    }, 0)
    return Math.round((totalProgress / execNodes.length) * 100)
  }, [execNodes, phases])

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const onStart = async () => {
    if (!plan) return
    if (execStatus === 'running') return
    if (!execNodes.length) return
    if (startedRef.current) return
    startedRef.current = true

    setExecStatus('running')
    setStatusText('正在开始执行…')
    setPhases({})
    setCurrentItemId(null)

    const payload: ExecuteRequest = {
      plan_id: plan.plan_id,
      steps: execNodes.map((n) => ({
        item_id: n.id,
        item_type: n.type,
        start_time: n.start_time,
        end_time: n.end_time,
        commute_mode: n.type === 'commute' ? (n.commute_mode ?? null) : null,
      })),
    }

    try {
      const { execution_id } = await executeStart(payload)
      executionIdRef.current = execution_id

      const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
      const url = buildApiUrl(`/execute/events/${execution_id}`, base)
      const es = new EventSource(url)
      esRef.current = es

      es.onmessage = (ev) => {
        let parsed: ExecuteEvent | null = null
        try {
          parsed = JSON.parse(ev.data) as ExecuteEvent
        } catch {
          return
        }

        if (parsed.type === 'item_update') {
          const d = parsed.data as Record<string, unknown>
          const phase = typeof d.phase === 'string' ? d.phase : null
          const message = typeof d.message === 'string' ? d.message : null
          const itemId = typeof d.item_id === 'string' ? d.item_id : null

          if (itemId && (phase === 'checking' || phase === 'reserving')) {
            setCurrentItemId(itemId)
          }
          if (itemId && phase === 'done') {
            setCurrentItemId((prev) => (prev === itemId ? null : prev))
          }

          if (message && (phase === 'checking' || phase === 'reserving')) {
            setStatusText(message)
          } else if (phase === 'done' && itemId) {
            const node = execNodes.find((n) => n.id === itemId) ?? null
            if (node?.type === 'commute') {
              setStatusText('出租车已预定，正在同步其它预定进度…')
            } else {
              setStatusText(`已完成「${node?.title ?? itemId}」预定，正在同步其它预定进度…`)
            }
          }

          if (itemId && (phase === 'checking' || phase === 'reserving' || phase === 'done')) {
            setPhases((prev) => ({
              ...prev,
              [itemId]:
                phase === 'checking'
                  ? 'checking'
                  : phase === 'reserving'
                    ? 'reserving'
                    : phase === 'done'
                      ? 'done'
                      : prev[itemId] ?? 'waiting',
            }))
          }
        }

        if (parsed.type === 'done') {
          setExecStatus('done')
          setStatusText('执行完成')
          setCurrentItemId(null)
          setPhases(() => {
            const next: Record<string, ExecPhase> = {}
            for (const n of execNodes) next[n.id] = 'done'
            return next
          })
          es.close()
          esRef.current = null
        }
      }

      es.onerror = () => {
        startedRef.current = false
        setExecStatus('error')
        setStatusText('连接中断，请重试')
        es.close()
        esRef.current = null
      }
    } catch (e) {
      const raw = e instanceof Error ? e.message : '请求失败'
      startedRef.current = false
      setExecStatus('error')
      setStatusText(`请求失败：${raw}`)
    }
  }

  const onPause = () => {
    if (!esRef.current) return
    esRef.current.close()
    esRef.current = null
    setExecStatus('paused')
    setStatusText('已暂停执行')
  }

  const onResume = () => {
    if (execStatus !== 'paused') return
    startedRef.current = false
    void onStart()
  }

  const shortenTitle = (title: string, id: string) => {
    const trimmed = title.trim()
    if (expandedIds[id]) return trimmed
    return trimmed
  }

  const phaseText = (phase: ExecPhase) => {
    if (phase === 'checking') return '正在检查预约'
    if (phase === 'reserving') return '正在预约'
    if (phase === 'done') return '预约完成'
    return '等待开始'
  }

  useEffect(() => {
    return () => {
      esRef.current?.close()
      esRef.current = null
    }
  }, [])

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

  return (
    <main className="min-h-screen bg-[#F7F8FC] px-5 pt-14 pb-40">
      <div className="mx-auto max-w-[430px]">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="h-10 w-10 rounded-full bg-white border border-slate-100 flex items-center justify-center"
            aria-label="返回"
          >
            <ChevronLeft className="h-5 w-5 text-slate-700" />
          </button>
          <div className="inline-flex items-center gap-2 text-base font-semibold text-slate-900">
            {execStatus === 'done' ? (
              <>
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                <span>执行完成</span>
              </>
            ) : (
              <span>执行中</span>
            )}
          </div>
          <button
            type="button"
            className="h-10 w-10 rounded-full bg-white border border-slate-100 flex items-center justify-center"
            aria-label="帮助"
          >
            <HelpCircle className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        <div className="mt-4 text-sm font-semibold text-slate-900">
          让我们开始今天的行程吧
        </div>

        <div className="mt-5 rounded-3xl bg-white p-4 shadow-sm border border-slate-100">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-slate-900">
              已完成 {doneCount}/{total || 0}
            </div>
            <div className="text-sm font-semibold text-blue-600">{progress}%</div>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-500 to-blue-600 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-3 text-xs text-slate-600">
            <span className="text-slate-500">当前：</span>
            {statusText}
          </div>
        </div>

        <div className="mt-4 rounded-3xl bg-white p-4 shadow-sm border border-slate-100">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-slate-900">行程安排</div>
            <div className="text-xs text-slate-500">共 {execNodes.length} 个节点</div>
          </div>

          <div className="mt-3 space-y-2">
            {execNodes.map((s, idx) => {
              const phase = phases[s.id] ?? 'waiting'
              const isActive = s.id === currentItemId
              let pill = { label: '待执行', cls: 'bg-slate-50 text-slate-600 border-slate-100' }
              if (phase === 'done') pill = { label: '已完成', cls: 'bg-emerald-50 text-emerald-700 border-emerald-100' }
              else if (isActive || phase === 'checking' || phase === 'reserving') {
                pill = { label: '进行中', cls: 'bg-blue-50 text-blue-700 border-blue-100' }
              }

              const showDot = phase === 'done' || isActive || idx < doneCount
              const dotCls = phase === 'done' ? 'bg-emerald-500' : isActive ? 'bg-blue-600' : 'bg-slate-200'
              const compactTitle = shortenTitle(s.title, s.id)

              return (
                <div key={s.id} className="flex items-start gap-3">
                  <div className={['w-12 text-xs font-semibold', isActive ? 'text-blue-600' : 'text-slate-600'].join(' ')}>
                    {s.start_time}
                  </div>

                  <div className="relative flex w-4 justify-center pt-1">
                    <div className="absolute top-1 bottom-0 w-px bg-slate-200" />
                    {showDot ? (
                      <div className={`relative z-10 h-3 w-3 rounded-full ${dotCls}`} />
                    ) : (
                      <div className="relative z-10 h-3 w-3 rounded-full border border-slate-200 bg-white" />
                    )}
                  </div>

                  <div className="flex-1 rounded-2xl border border-slate-100 bg-white p-3">
                    <div className="flex items-start justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => toggleExpanded(s.id)}
                        className="text-left text-sm font-semibold text-slate-900"
                      >
                        {compactTitle}
                      </button>
                      <div className={`shrink-0 rounded-full border px-2 py-1 text-[11px] font-semibold ${pill.cls}`}>
                        {pill.label}
                      </div>
                    </div>
                    {s.sub_title && s.sub_title !== s.title ? (
                      <div className="mt-1 text-xs text-slate-500">{s.sub_title}</div>
                    ) : null}
                    <div className="mt-1 text-[11px] text-slate-400">{phaseText(phase)}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {execStatus === 'done' ? (
        <div className="fixed bottom-0 left-0 right-0 z-30 mx-auto max-w-[430px] rounded-t-[28px] bg-white/90 px-5 pb-6 pt-4 shadow-2xl backdrop-blur border-t border-slate-100">
          <div className="grid grid-cols-3 gap-3">
            <button
              type="button"
              className="h-12 rounded-2xl text-sm font-semibold border bg-white border-slate-200 text-slate-700"
            >
              分享行程
            </button>
            <button
              type="button"
              className="h-12 rounded-2xl text-sm font-semibold border bg-white border-slate-200 text-slate-700"
            >
              预定提醒
            </button>
            <button
              type="button"
              onClick={() => navigate(`/app/journey/${plan.plan_id}`)}
              className="h-12 rounded-2xl bg-slate-900 text-white text-sm font-semibold"
            >
              进入流程
            </button>
          </div>
        </div>
      ) : (
        <div className="fixed bottom-0 left-0 right-0 z-30 mx-auto max-w-[430px] rounded-t-[28px] bg-white/90 px-5 pb-6 pt-4 shadow-2xl backdrop-blur border-t border-slate-100">
          <button
            type="button"
            onClick={execStatus === 'running' ? onPause : execStatus === 'paused' ? onResume : onStart}
            disabled={!execNodes.length}
            className={[
              'h-12 w-full rounded-2xl text-sm font-semibold',
              !execNodes.length
                ? 'bg-slate-200 text-slate-500'
                : execStatus === 'running'
                  ? 'bg-white border border-slate-200 text-slate-700'
                  : 'bg-slate-900 text-white',
            ].join(' ')}
          >
            {execStatus === 'idle'
              ? '开始流程'
              : execStatus === 'paused'
                ? '继续执行'
                : execStatus === 'running'
                  ? '暂停执行'
                  : '开始执行'}
          </button>
        </div>
      )}
    </main>
  )
}

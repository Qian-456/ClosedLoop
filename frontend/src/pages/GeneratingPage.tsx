import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Database, CheckCircle2, Loader2 } from 'lucide-react'
import { invoke } from '../features/itinerary/api/invoke'
import { useItineraryStore } from '../features/itinerary/store/useItineraryStore'
import { sleep } from '../shared/lib/sleep'
import Skeleton from '../shared/ui/Skeleton'
import PrimaryButton from '../shared/ui/PrimaryButton'

type StepId = 'understand' | 'filter' | 'compose' | 'pack'

type Step = {
  id: StepId
  title: string
  subtitle: string
  holdMs?: number
}

export default function GeneratingPage() {
  const navigate = useNavigate()
  const userInput = useItineraryStore((s) => s.userInput)
  const setInvokeRunning = useItineraryStore((s) => s.setInvokeRunning)
  const setInvokeSuccess = useItineraryStore((s) => s.setInvokeSuccess)
  const setInvokeError = useItineraryStore((s) => s.setInvokeError)
  const invokeStatus = useItineraryStore((s) => s.invokeStatus)
  const errorMessage = useItineraryStore((s) => s.errorMessage)

  const steps = useMemo<Step[]>(
    () => [
      {
        id: 'understand',
        title: '理解需求',
        subtitle: '已理解出行人数、时长、预算与偏好',
      },
      {
        id: 'filter',
        title: '筛选候选',
        subtitle: '已从上千个景点与活动中筛选合适选项',
        holdMs: 1500,
      },
      {
        id: 'compose',
        title: '组合路线与预算',
        subtitle: '已组合出多套路线的体验与顺序',
        holdMs: 1500,
      },
      {
        id: 'pack',
        title: '整理方案',
        subtitle: '正在优化呈现与细节，即将完成',
      },
    ],
    [],
  )

  const [activeIdx, setActiveIdx] = useState(0)
  const [progress, setProgress] = useState(10)
  const mountedRef = useRef(false)

  useEffect(() => {
    if (mountedRef.current) return
    mountedRef.current = true

    const run = async () => {
      if (!userInput.trim()) {
        navigate('/app')
        return
      }

      setInvokeRunning()

      const invokePromise = invoke(userInput.trim())
      const progressPromise = (async () => {
        setProgress(18)
        for (let i = 0; i < steps.length; i += 1) {
          setActiveIdx(i)
          setProgress(18 + i * 18)
          const hold = steps[i].holdMs ?? 800
          await sleep(hold)
        }
        setProgress(82)
      })()

      try {
        const [resp] = await Promise.all([invokePromise, progressPromise])
        setInvokeSuccess(resp.state)
        setProgress(100)
        await sleep(350)
        navigate('/app/plans')
      } catch (e) {
        const raw = e instanceof Error ? e.message : '请求失败'
        const hint =
          raw.includes('502') || raw.toLowerCase().includes('fetch')
            ? '后端服务不可用（请确认 FastAPI 已启动在 127.0.0.1:8000）。'
            : '请求失败，请重试。'
        setInvokeError(`${hint} 错误：${raw}`)
        setProgress(20)
      }
    }

    void run()
  }, [
    navigate,
    setInvokeError,
    setInvokeRunning,
    setInvokeSuccess,
    steps,
    userInput,
  ])

  const isError = invokeStatus === 'error'

  const onRetry = () => {
    navigate(0)
  }

  return (
    <main className="min-h-screen bg-[#F7F8FC] px-5 pt-14 pb-10">
      <div className="mx-auto max-w-[430px]">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            行程方案
          </h1>
          <span className="text-xs font-medium px-2 py-1 rounded-full bg-sky-50 text-sky-700 border border-sky-100">
            Mock 展示
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          正在根据你的需求生成 3 套可比较方案
        </p>

        <div className="mt-4 flex items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 rounded-full border bg-white px-2 py-1 text-slate-600">
            <Database className="h-3.5 w-3.5" />
            数据来源 Mock
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border bg-white px-2 py-1 text-slate-600">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            生成中
          </span>
        </div>

        <div className="mt-5 rounded-3xl bg-white p-4 shadow-sm border border-slate-100">
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>Agent 正在生成方案</span>
            <span>{progress}%</span>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-sky-500 to-blue-600 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="mt-4 space-y-3">
            {steps.map((s, idx) => {
              const done = idx < activeIdx
              const active = idx === activeIdx
              return (
                <div key={s.id} className="flex gap-3">
                  <div className="mt-0.5">
                    {done ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : (
                      <div className="h-5 w-5 rounded-full border border-slate-200 flex items-center justify-center">
                        {active ? (
                          <div className="h-2.5 w-2.5 rounded-full bg-blue-600" />
                        ) : (
                          <div className="h-2.5 w-2.5 rounded-full bg-slate-200" />
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-medium text-slate-900">
                        {s.title}
                      </div>
                      {active && !done ? (
                        <div className="text-xs text-slate-400">...</div>
                      ) : null}
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {s.subtitle}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="mt-6 space-y-3">
          <div className="rounded-3xl bg-white p-4 shadow-sm border border-slate-100">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
            <div className="mt-4 flex gap-3">
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
            </div>
            <div className="mt-4 flex gap-4">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-24" />
            </div>
          </div>

          <div className="rounded-3xl bg-white p-4 shadow-sm border border-slate-100 opacity-90">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
            <div className="mt-4 flex gap-3">
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
            </div>
          </div>

          <div className="rounded-3xl bg-white p-4 shadow-sm border border-slate-100 opacity-70">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
            <div className="mt-4 flex gap-3">
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <Skeleton className="h-12 w-12 rounded-2xl" />
            </div>
          </div>
        </div>

        {isError ? (
          <div className="mt-6 rounded-3xl bg-white p-4 shadow-sm border border-red-100">
            <div className="text-sm font-semibold text-slate-900">
              生成失败
            </div>
            <div className="mt-1 text-xs text-slate-500 break-words">
              {errorMessage || '请求失败，请重试'}
            </div>
            <div className="mt-4">
              <PrimaryButton label="重试" onClick={onRetry} />
            </div>
          </div>
        ) : null}
      </div>
    </main>
  )
}

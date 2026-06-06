import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { JourneyView } from '../features/itinerary/ui/JourneyView'
import { PhoneShell } from '../shared/ui/PhoneShell'
import type { ItineraryPlanVariant, ItineraryStep } from '../features/itinerary/model/types'

type ShareSnapshot = {
  id: string
  title: string
  total_cost: number
  total_duration_minutes: number
  selected_item_ids?: string[]
  average_score?: number
  experience_score?: number
  steps: ItineraryStep[]
  created_at: string
}

function snapshotToPlan(snapshot: ShareSnapshot): ItineraryPlanVariant {
  return {
    plan_id: snapshot.id,
    title: snapshot.title,
    steps: snapshot.steps,
    selected_item_ids: snapshot.selected_item_ids ?? snapshot.steps.map((step) => step.item.id),
    total_duration_minutes: snapshot.total_duration_minutes,
    total_cost: snapshot.total_cost,
    average_score: snapshot.average_score ?? 0,
    experience_score: snapshot.experience_score,
  }
}

export default function SharePage() {
  const { shareId } = useParams()
  const snapshot = useMemo<ShareSnapshot | null>(() => {
    if (!shareId) return null
    try {
      const raw = window.localStorage.getItem(`closedloop-share-${shareId}`)
      if (!raw) return null
      return JSON.parse(raw) as ShareSnapshot
    } catch {
      return null
    }
  }, [shareId])

  if (!snapshot) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#EEF2F7] px-3 py-3">
        <PhoneShell onBack={() => window.history.back()} onClose={() => window.history.back()}>
          <div className="flex h-full items-center justify-center bg-[#F6F7FB] px-5">
            <div className="w-full rounded-[8px] border border-slate-200 bg-white px-5 py-8 text-center shadow-sm">
              <div className="text-lg font-black text-slate-950">分享内容不存在或已过期</div>
              <div className="mt-2 text-sm text-slate-500">请确认链接来自当前演示设备。</div>
            </div>
          </div>
        </PhoneShell>
      </main>
    )
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#EEF2F7] px-3 py-3">
      <PhoneShell onBack={() => window.history.back()} onClose={() => window.history.back()}>
        <JourneyView plan={snapshotToPlan(snapshot)} mode="share" title="分享行程" fitContainer showHeader={false} />
      </PhoneShell>
    </main>
  )
}

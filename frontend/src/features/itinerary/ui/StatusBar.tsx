import { ChevronDown, ChevronUp } from 'lucide-react'

import type { BubbleEntry, ProcessBubblePhase } from '../model/types'
import { ProcessPanel } from './ProcessPanel'

type Props = {
  status:
    | {
        phase: ProcessBubblePhase
        text: string
      }
    | null
  displayItems: BubbleEntry[]
  expanded: boolean
  onToggleExpanded: () => void
  visible: boolean
}

/**
 * Displays the current lightweight streaming status for the active session.
 */
export function StatusBar({ status, displayItems, expanded, onToggleExpanded, visible }: Props) {
  if (!visible || !status) {
    return null
  }

  return (
    <div className="px-4 pt-3">
      <div className="rounded-2xl border border-blue-100 bg-blue-50/80 px-4 py-3 text-sm text-blue-700 shadow-sm">
        <button
          type="button"
          onClick={onToggleExpanded}
          className="flex w-full items-center justify-between gap-3 text-left"
        >
          <span>{status.text}</span>
          <span className="shrink-0 text-blue-500">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </span>
        </button>

        {expanded ? (
          <div className="mt-3">
            <ProcessPanel items={displayItems} />
          </div>
        ) : null}
      </div>
    </div>
  )
}

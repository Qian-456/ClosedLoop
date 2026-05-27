import { Bot, ChevronDown, ChevronUp } from 'lucide-react'

import type { ProcessBubbleRecord } from '../model/types'
import { ProcessPanel } from './ProcessPanel'

type Props = {
  bubble: ProcessBubbleRecord
  onToggleExpanded: (bubbleId: string) => void
}

/**
 * Renders the in-chat process bubble between user input and AI response.
 */
export function ProcessBubble({ bubble, onToggleExpanded }: Props) {
  const statusToneClass =
    bubble.status === 'failed'
      ? 'border-rose-200 bg-rose-50 text-rose-700'
      : bubble.status === 'success'
        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
        : 'border-blue-100 bg-blue-50/80 text-blue-700'

  return (
    <div className="flex gap-3 max-w-[85%] mr-auto">
      <div className="w-8 h-8 rounded-full bg-white border border-slate-100 text-blue-600 flex items-center justify-center shrink-0 shadow-sm">
        <Bot className="w-5 h-5" />
      </div>
      <div className={`flex-1 rounded-2xl border px-4 py-3 shadow-sm ${statusToneClass}`}>
        <button
          type="button"
          onClick={() => onToggleExpanded(bubble.id)}
          className="flex w-full items-center justify-between gap-3 text-left"
        >
          <span className="text-sm leading-6">{bubble.text}</span>
          <span className="shrink-0">
            {bubble.expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </span>
        </button>

        {bubble.expanded ? (
          <div className="mt-3">
            <ProcessPanel items={bubble.processItems} />
          </div>
        ) : null}
      </div>
    </div>
  )
}

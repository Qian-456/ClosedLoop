import type { BubbleEntry } from '../model/types'

type Props = {
  items: BubbleEntry[]
}

function statusLabel(status: BubbleEntry['status']): string {
  if (status === 'success') return '已完成'
  if (status === 'failed') return '失败'
  return '进行中'
}

/**
 * Displays expandable process details grouped by tool execution.
 */
export function ProcessPanel({ items }: Props) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl bg-white/70 px-3 py-3 text-xs text-slate-500 shadow-sm">
        当前还没有过程详情。
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div
          key={`${item.kind}-${item.tool ?? item.title}-${index}`}
          className="rounded-2xl bg-white/80 px-3 py-3 text-xs text-slate-600 shadow-sm"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="font-medium text-slate-800">{item.title}</div>
            {item.status ? (
              <div className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
                {statusLabel(item.status)}
              </div>
            ) : null}
          </div>
          <div className="mt-1 leading-5 text-slate-600">{item.summary}</div>
          {item.meta && item.meta.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {item.meta.map((meta) => (
                <span
                  key={`${item.kind}-${item.tool ?? item.title}-${meta}`}
                  className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-500"
                >
                  {meta}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  )
}

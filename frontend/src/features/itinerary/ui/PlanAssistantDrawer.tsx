import { useMemo, useState } from 'react'
import BottomDrawer from '../../../shared/ui/BottomDrawer'
import Chip from '../../../shared/ui/Chip'
import PrimaryButton from '../../../shared/ui/PrimaryButton'

type Variant = 'plans' | 'detail'

type Props = {
  variant: Variant
  bottomOffset?: number
  onSubmit?: (text: string) => void
  primaryAction?: {
    label: string
    onClick: () => void
  }
}

export default function PlanAssistantDrawer({
  variant,
  bottomOffset,
  onSubmit,
  primaryAction,
}: Props) {
  const [value, setValue] = useState('')
  const [inputOpen, setInputOpen] = useState(false)

  const spec = useMemo(() => {
    if (variant === 'detail') {
      return {
        collapsedHeight: primaryAction ? 220 : 176,
        title: '调整当前方案',
        subtitle: '告诉我你想怎么优化这个行程',
        chips: ['减少步行', '晚餐换更重点', '礼物提前', '增加拍照点', '小孩午睡时间', '放慢节奏'],
      }
    }

    return {
      collapsedHeight: 184,
      title: '三个都不满意？',
      subtitle: '告诉我你想怎么调整，我重新生成 3 套方案',
      chips: ['更适合小孩', '少走路', '降预算', '更轻松', '室内为主', '增加惊喜感'],
    }
  }, [primaryAction, variant])

  const onSend = () => {
    const trimmed = value.trim()
    if (!trimmed) return
    setValue('')
    setInputOpen(false)
    if (onSubmit) onSubmit(trimmed)
  }

  return (
    <BottomDrawer
      collapsedHeight={spec.collapsedHeight}
      expandedHeight={440}
      bottomOffset={bottomOffset}
      toggleLabel="展开或收起调整抽屉"
      header={
      <div className="flex items-start gap-3">
        <img src="/robot.png" alt="机器人" className="h-10 w-10 rounded-2xl bg-slate-50 border border-slate-100 object-cover" />
        <div className="flex-1">
          <div className="text-sm font-semibold text-slate-900">{spec.title}</div>
          <div className="mt-0.5 text-xs text-slate-500">{spec.subtitle}</div>
          {variant === 'plans' ? (
            <div className="mt-1 text-[11px] text-slate-400 leading-snug whitespace-normal break-words">
              <span className="block">选择一个最合适的方案以便整体安排。</span>
              <span className="block">如需局部调整，可在后续步骤进行。</span>
            </div>
          ) : null}

          <div className="mt-2 flex items-center gap-2">
            {variant === 'plans' && !inputOpen ? (
              <button
                type="button"
                onClick={() => setInputOpen(true)}
                className="h-11 w-full rounded-full border border-slate-200 bg-white px-4 text-left text-sm text-slate-500 hover:border-slate-300 flex items-center justify-between"
                aria-label="打开输入框"
              >
                <span>点一下再输入…</span>
                <span className="h-8 w-8 rounded-full bg-slate-900 text-white text-sm font-semibold flex items-center justify-center">
                  ↑
                </span>
              </button>
            ) : (
              <>
                <input
                  aria-label="输入你的想法"
                  placeholder="或者直接告诉我你的想法…"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  className="h-11 flex-1 rounded-full border border-slate-200 bg-white px-4 text-base text-slate-900 outline-none focus:border-blue-300"
                />
                <button
                  type="button"
                  onClick={onSend}
                  className="h-11 w-11 rounded-full bg-slate-900 text-white text-sm font-semibold"
                  aria-label="发送"
                >
                  ↑
                </button>
              </>
            )}
          </div>

          {primaryAction ? (
            <div className="mt-3">
              <PrimaryButton label={primaryAction.label} onClick={primaryAction.onClick} />
            </div>
          ) : null}
        </div>
      </div>
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {spec.chips.map((c) => (
            <Chip
              key={c}
              label={c}
              onClick={() => setValue((prev) => (prev.trim() ? `${prev.trim()} ${c}` : c))}
            />
          ))}
        </div>
      </div>
    </BottomDrawer>
  )
}

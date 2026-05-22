import { useEffect, useMemo, useRef, useState } from 'react'

type Props = {
  collapsedHeight?: number
  expandedHeight?: number
  defaultExpanded?: boolean
  bottomOffset?: number
  toggleLabel?: string
  header: React.ReactNode
  children?: React.ReactNode
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n))
}

export default function BottomDrawer({
  collapsedHeight = 132,
  expandedHeight = 420,
  defaultExpanded = false,
  bottomOffset = 0,
  toggleLabel = '展开或收起抽屉',
  header,
  children,
}: Props) {
  const collapsedTranslate = useMemo(
    () => Math.max(0, expandedHeight - collapsedHeight),
    [collapsedHeight, expandedHeight],
  )

  const [expanded, setExpanded] = useState(defaultExpanded)
  const [translateY, setTranslateY] = useState(defaultExpanded ? 0 : collapsedTranslate)
  const [dragging, setDragging] = useState(false)
  const translateRef = useRef(translateY)

  const dragRef = useRef<{
    pointerId: number | null
    startY: number
    startTranslate: number
  }>({ pointerId: null, startY: 0, startTranslate: 0 })

  useEffect(() => {
    setTranslateY(expanded ? 0 : collapsedTranslate)
  }, [collapsedTranslate, expanded])

  useEffect(() => {
    translateRef.current = translateY
  }, [translateY])

  return (
    <div className="fixed left-0 right-0 z-30 pointer-events-none" style={{ bottom: bottomOffset }}>
      <div
        className={[
          'mx-auto max-w-[430px] rounded-t-[28px] bg-white/92 px-5 pb-6 pt-3 shadow-2xl backdrop-blur border-t border-slate-100 pointer-events-auto',
          dragging ? '' : 'transition-transform duration-300 ease-out',
        ].join(' ')}
        style={{
          height: expandedHeight,
          transform: `translateY(${translateY}px)`,
        }}
      >
        <button
          type="button"
          aria-label={toggleLabel}
          className="mx-auto block py-2"
          style={{ touchAction: 'none' }}
          onClick={() => setExpanded((v) => !v)}
          onPointerDown={(e) => {
            if (e.button != null && e.button !== 0) return
            dragRef.current.pointerId = e.pointerId
            dragRef.current.startY = e.clientY
            dragRef.current.startTranslate = translateY
            setDragging(true)
            e.currentTarget.setPointerCapture(e.pointerId)
          }}
          onPointerMove={(e) => {
            if (!dragging) return
            if (dragRef.current.pointerId !== e.pointerId) return
            const delta = e.clientY - dragRef.current.startY
            const next = clamp(dragRef.current.startTranslate + delta, 0, collapsedTranslate)
            setTranslateY(next)
          }}
          onPointerUp={(e) => {
            if (!dragging) return
            if (dragRef.current.pointerId !== e.pointerId) return
            setDragging(false)
            dragRef.current.pointerId = null
            const threshold = collapsedTranslate / 2
            setExpanded(translateRef.current <= threshold)
          }}
          onPointerCancel={() => {
            setDragging(false)
            dragRef.current.pointerId = null
            setTranslateY(expanded ? 0 : collapsedTranslate)
          }}
        >
          <div className="mx-auto h-1.5 w-10 rounded-full bg-slate-200" />
        </button>

        <div>{header}</div>

        <div className={expanded ? 'mt-4' : 'mt-4 hidden'}>{children}</div>
      </div>
    </div>
  )
}

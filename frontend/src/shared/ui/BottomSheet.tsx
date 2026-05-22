import { useEffect } from 'react'

type Props = {
  open: boolean
  title?: string
  onClose: () => void
  children: React.ReactNode
}

export default function BottomSheet({ open, title, onClose, children }: Props) {
  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose, open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
        aria-label="关闭"
      />
      <div className="absolute bottom-0 left-0 right-0 mx-auto max-w-[430px] rounded-t-[28px] bg-white p-5 shadow-2xl">
        <div className="mx-auto h-1.5 w-10 rounded-full bg-slate-200" />
        {title ? (
          <div className="mt-3 text-base font-semibold text-slate-900">
            {title}
          </div>
        ) : null}
        <div className="mt-4">{children}</div>
      </div>
    </div>
  )
}


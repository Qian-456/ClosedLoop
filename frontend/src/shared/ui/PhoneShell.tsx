import { ChevronLeft, X } from 'lucide-react'
import type { ReactNode } from 'react'

type PhoneShellProps = {
  children: ReactNode
  onBack?: () => void
  onClose?: () => void
}

export function PhoneShell({ children, onBack, onClose }: PhoneShellProps) {
  return (
    <div className="relative mx-auto h-[min(884px,calc(100vh-20px))] w-[min(430px,calc(100vw-20px))] rounded-[44px] border-[10px] border-black bg-black shadow-[0_28px_90px_rgba(15,23,42,0.22)]">
      <div className="absolute left-[-14px] top-[190px] h-16 w-1.5 rounded-l-full bg-black" />
      <div className="absolute right-[-14px] top-[300px] h-24 w-1.5 rounded-r-full bg-black" />

      <div className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-[34px] bg-[#F6F7FB]">
        <div className="relative z-30 flex h-16 shrink-0 items-center justify-between border-b border-slate-100 bg-white/90 px-4 backdrop-blur">
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-600"
            onClick={onBack}
            aria-label="返回"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <div className="absolute left-1/2 top-4 h-9 w-32 -translate-x-1/2 rounded-full bg-black" />
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-500"
            onClick={onClose}
            aria-label="关闭"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
      </div>
    </div>
  )
}

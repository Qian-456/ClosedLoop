import { clsx } from 'clsx'

type Props = {
  children: React.ReactNode
  className?: string
}

export default function IconBadge({ children, className }: Props) {
  return (
    <div
      className={clsx(
        'h-11 w-11 rounded-2xl bg-white/80 ring-1 ring-white/60 shadow-sm flex items-center justify-center',
        className,
      )}
    >
      {children}
    </div>
  )
}


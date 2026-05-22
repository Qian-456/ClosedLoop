import { clsx } from 'clsx'

type Props = {
  label: string
  onClick?: () => void
  active?: boolean
}

export default function Chip({ label, onClick, active }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm',
        'bg-white/70 backdrop-blur border-white/60 shadow-sm',
        active ? 'ring-2 ring-blue-500/30' : 'hover:bg-white',
      )}
    >
      <span className="text-slate-700">{label}</span>
    </button>
  )
}


import { clsx } from 'clsx'

type Props = {
  label: string
  onClick?: () => void
  disabled?: boolean
  className?: string
}

export default function PrimaryButton({
  label,
  onClick,
  disabled,
  className,
}: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'h-14 w-full rounded-full px-5 text-base font-semibold text-white',
        'bg-gradient-to-b from-slate-900 to-slate-950 shadow-xl shadow-slate-900/15',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        className,
      )}
    >
      {label}
    </button>
  )
}


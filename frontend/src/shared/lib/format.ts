export function formatMoney(amount: number): string {
  if (!Number.isFinite(amount)) return '--'
  const rounded = Math.round(amount)
  return `¥${rounded}`
}

export function formatMoneyExact(amount: number): string {
  if (!Number.isFinite(amount)) return '--'
  const rounded = Math.round(amount * 100) / 100
  return `¥${rounded.toFixed(2)}`
}

export function formatDurationMinutes(totalMinutes: number): string {
  if (!Number.isFinite(totalMinutes) || totalMinutes <= 0) return '--'
  const hours = Math.floor(totalMinutes / 60)
  const mins = totalMinutes % 60
  if (hours <= 0) return `${mins}m`
  if (mins <= 0) return `${hours}h`
  return `${hours}h ${mins}m`
}

export function parseTimeToMinutes(hhmm: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm.trim())
  if (!m) return null
  const h = Number(m[1])
  const mm = Number(m[2])
  if (!Number.isFinite(h) || !Number.isFinite(mm)) return null
  if (h < 0 || h > 23 || mm < 0 || mm > 59) return null
  return h * 60 + mm
}

export function minutesToTime(totalMinutes: number): string {
  const m = ((totalMinutes % (24 * 60)) + 24 * 60) % (24 * 60)
  const h = Math.floor(m / 60)
  const mm = m % 60
  return `${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
}

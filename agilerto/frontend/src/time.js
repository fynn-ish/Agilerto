// Small helpers for showing timestamps. Server times are UTC ISO strings ending in Z.
export function timeAgo(iso, nowMs) {
  const t = Date.parse(iso)
  if (!iso || Number.isNaN(t)) return 'never'
  const mins = Math.max(0, Math.round((nowMs - t) / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.floor(mins / 60)
  if (hours < 48) return `${hours} h ago`
  return `${Math.floor(hours / 24)} days ago`
}

export function clock(iso) {
  const t = Date.parse(iso)
  if (!iso || Number.isNaN(t)) return ''
  return new Date(t).toLocaleString('en-PH', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function dayLabel(dateStr, index) {
  if (index === 0) return 'Today'
  const d = new Date(`${dateStr}T00:00:00`)
  return Number.isNaN(d.getTime()) ? dateStr : d.toLocaleDateString('en-PH', { weekday: 'short' })
}

export const round = (v, digits = 0) =>
  v === null || v === undefined ? '–' : digits ? Number(v).toFixed(digits) : Math.round(v)

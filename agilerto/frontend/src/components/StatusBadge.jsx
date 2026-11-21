import { describeStatus } from '../status'

// Online/Offline dot + words (never color alone) + how fresh the saved data is.
export default function StatusBadge({ dash }) {
  const { tone, label, detail } = describeStatus(dash)
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
      <span className="inline-flex items-center gap-1.5 font-bold">
        <span aria-hidden="true" className={`inline-block h-3 w-3 rounded-full ${tone === 'green' ? 'bg-evac' : 'bg-amber-600'}`} />
        {label}
      </span>
      <span className="text-sm text-muted">{detail}</span>
    </p>
  )
}

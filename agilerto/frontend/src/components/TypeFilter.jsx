import { FACILITY_TYPES } from '../constants'

export default function TypeFilter({ active, counts, onToggle }) {
  return (
    <div role="group" aria-label="Filter by facility type" className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
      {FACILITY_TYPES.map((t) => {
        const on = active.has(t.key)
        return (
          <button
            key={t.key}
            type="button"
            aria-pressed={on}
            onClick={() => onToggle(t.key)}
            className={`inline-flex min-h-11 items-center gap-2 rounded-md border-2 px-2 text-sm sm:px-3 sm:text-base ${
              on ? 'bg-white font-bold' : 'border-line bg-transparent text-muted'
            }`}
            style={on ? { borderColor: t.color } : undefined}
          >
            <span
              aria-hidden="true"
              className="grid h-6 w-6 place-items-center rounded text-sm font-bold text-white"
              style={{ background: on ? t.color : '#8a949c' }}
            >
              {t.letter}
            </span>
            {t.label}
            <span className="tabular-nums text-muted">{counts[t.key] ?? 0}</span>
          </button>
        )
      })}
    </div>
  )
}

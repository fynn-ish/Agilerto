import { useEffect, useRef } from 'react'
import { TYPE_BY_KEY } from '../constants'

export default function FacilityList({ facilities, selectedId, onSelect }) {
  const selectedRef = useRef(null)

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: 'nearest' })
  }, [selectedId])

  if (!facilities.length) {
    return (
      <p className="rounded-md border border-line bg-white p-4">
        No facilities of the selected types within this radius. Try a larger radius, turn on more
        types, or choose another location.
      </p>
    )
  }

  return (
    <ul className="space-y-2">
      {facilities.map((f) => {
        const t = TYPE_BY_KEY[f.type]
        const selected = f.id === selectedId
        return (
          <li key={f.id} ref={selected ? selectedRef : null}>
            <div
              className={`rounded-md border-2 bg-white p-3 ${selected ? 'border-ink' : 'border-transparent'}`}
              style={{ boxShadow: `inset 6px 0 0 ${t.color}` }}
            >
              <button
                type="button"
                onClick={() => onSelect(f.id)}
                aria-pressed={selected}
                className="block w-full pl-2 text-left"
              >
                <span className="flex items-baseline justify-between gap-3">
                  <span className="text-lg font-bold leading-snug">{f.name}</span>
                  <span className="shrink-0 text-lg font-bold tabular-nums">{f.distance_km} km</span>
                </span>
                <span className="block text-sm text-muted">{t.single}</span>
              </button>

              <div className="space-y-1 pl-2 pt-1 text-base">
                {f.address && <p>{f.address}</p>}
                {f.capacity && <p>Capacity: about {f.capacity} people</p>}
                {f.phone && (
                  <p>
                    <a className="font-bold text-brand underline underline-offset-4"
                       href={`tel:${f.phone.replace(/[^\d+]/g, '')}`}>
                      {f.phone}
                    </a>
                  </p>
                )}
                {!f.verified && (
                  <p className="inline-block rounded bg-amber-100 px-2 py-0.5 text-sm text-amber-950">
                    Unverified
                  </p>
                )}
              </div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

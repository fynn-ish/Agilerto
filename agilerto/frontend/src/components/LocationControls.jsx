import { useState } from 'react'
import { PLACES, RADIUS_OPTIONS } from '../constants'

const GEO_ERRORS = {
  1: 'Location permission was denied. Choose your city below or tap the map.',
  2: 'Your device could not determine its location. Choose your city below or tap the map.',
  3: 'Finding your location timed out. Try again, choose your city, or tap the map.',
}

export default function LocationControls({ location, radius, onLocate, onRadius }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function useMyLocation() {
    setError('')
    if (!navigator.geolocation || !window.isSecureContext) {
      // Browsers only allow GPS on https or localhost, not on a plain http LAN address.
      setError('GPS is not available on this connection. Choose your city below or tap the map.')
      return
    }
    setBusy(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setBusy(false)
        onLocate({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          label: 'Your location',
          source: 'gps',
        })
      },
      (err) => {
        setBusy(false)
        setError(GEO_ERRORS[err.code] || GEO_ERRORS[2])
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    )
  }

  const select = 'min-h-11 w-full rounded-md border border-line bg-white px-3 text-base'

  return (
    <section aria-label="Choose location" className="space-y-2">
      <div className="flex flex-wrap items-end gap-3">
        <button
          type="button"
          onClick={useMyLocation}
          disabled={busy}
          className="min-h-11 w-full rounded-md bg-brand px-4 font-bold text-white hover:bg-brand-dark disabled:opacity-60 sm:w-auto"
        >
          {busy ? 'Finding you…' : 'Use my location'}
        </button>

        <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm text-muted sm:flex-none">
          Or choose a city
          <select
            className={select}
            value={location.source === 'manual' ? location.label : ''}
            onChange={(e) => {
              const p = PLACES.find((x) => x.name === e.target.value)
              if (p) onLocate({ lat: p.lat, lng: p.lng, label: p.name, source: 'manual' })
            }}
          >
            <option value="" disabled>Select…</option>
            {PLACES.map((p) => <option key={p.name}>{p.name}</option>)}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-muted">
          Search radius
          <select className={select} value={radius} onChange={(e) => onRadius(Number(e.target.value))}>
            {RADIUS_OPTIONS.map((r) => <option key={r} value={r}>{r} km</option>)}
          </select>
        </label>
      </div>

      <p className="text-sm text-muted" aria-live="polite">
        {location.source === 'default'
          ? <>Showing <strong className="text-ink">{location.label}</strong> by default. Use your location or tap the map to search elsewhere.</>
          : <>Searching around <strong className="text-ink">{location.label}</strong>.</>}
      </p>
      {error && <p role="alert" className="text-sm font-bold text-alarm">{error}</p>}
    </section>
  )
}

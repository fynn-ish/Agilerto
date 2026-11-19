import { useState } from 'react'
import { triggerRefresh } from '../api'
import { clock, round, timeAgo } from '../time'
import QuakeCard from './QuakeCard'
import WeatherCard from './WeatherCard'

function latest(a, b) {
  return [a, b].filter(Boolean).sort().pop() ?? null
}

// Online/offline status + weather + earthquakes. Collapsible so it doesn't push the map off small screens.
export default function ConditionsPanel({ dash }) {
  const { status, data, fromCache, savedAt, nowMs, reload } = dash
  const [open, setOpen] = useState(() => window.matchMedia('(min-width: 1024px)').matches)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  let tone = 'amber'
  let label = 'Offline'
  let detail = ''
  let lastSync = null

  if (status === 'loading') {
    label = 'Checking'
    detail = 'Loading saved conditions…'
  } else if (status === 'error' || !data) {
    detail = 'Conditions could not be loaded. Check that the backend is running.'
  } else {
    lastSync = latest(data.sources.weather.last_success_at, data.sources.earthquakes.last_success_at)
    if (fromCache) {
      label = 'Server unreachable'
      detail = `Showing a copy saved on this device (${clock(savedAt)}).`
    } else if (data.online) {
      tone = 'green'
      label = 'Online'
      detail = lastSync ? `Data refreshed ${timeAgo(lastSync, nowMs)}.` : 'No live data downloaded yet. Tap Refresh.'
    } else {
      detail = lastSync
        ? `Showing data saved ${clock(lastSync)} (${timeAgo(lastSync, nowMs)}).`
        : 'No live data saved yet. Connect to the internet once to download it.'
    }
  }

  const canRefresh = data && data.online && !fromCache
  async function refresh() {
    setBusy(true)
    setNote('')
    try {
      const r = await triggerRefresh()
      if (r.status === 'cooldown') setNote(`Please wait ${r.retry_in_seconds} s before refreshing again.`)
      else if (r.status === 'offline') setNote('No internet connection right now. Showing saved data.')
      else if (r.status === 'busy') setNote('A refresh is already running.')
      else if (r.weather?.ok === false || r.earthquakes?.ok === false) setNote('Some data could not be updated. Saved data is kept.')
      else setNote('Updated.')
      reload()
    } catch {
      setNote('Could not reach the server.')
    } finally {
      setBusy(false)
    }
  }

  const headline = data?.weather
    ? `${round(data.weather.current.temp_c)}°C ${data.weather.current.condition}`
    : null

  return (
    <details open={open} onToggle={(e) => setOpen(e.currentTarget.open)} className="rounded-md border border-line bg-white/60">
      <summary className="flex min-h-11 cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 [&::-webkit-details-marker]:hidden">
        <h2 className="text-lg font-bold">Current conditions</h2>
        <span className="inline-flex items-center gap-1.5 font-bold">
          <span
            aria-hidden="true"
            className={`inline-block h-3 w-3 rounded-full ${tone === 'green' ? 'bg-evac' : 'bg-amber-600'}`}
          />
          {label}
        </span>
        {!open && headline && <span className="text-muted">{headline}</span>}
        <span aria-hidden="true" className="ml-auto text-muted">{open ? 'Hide' : 'Show'}</span>
      </summary>

      <div className="space-y-3 border-t border-line p-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <p className="min-w-0 flex-1" aria-live="polite">{detail}</p>
          {canRefresh && (
            <button
              type="button"
              onClick={refresh}
              disabled={busy}
              className="min-h-11 rounded-md border-2 border-brand px-4 font-bold text-brand hover:bg-brand hover:text-white disabled:opacity-60"
            >
              {busy ? 'Refreshing…' : 'Refresh now'}
            </button>
          )}
        </div>
        {note && <p role="status" className="text-sm font-bold">{note}</p>}

        {data && (
          <div className="grid gap-3 md:grid-cols-2">
            <WeatherCard weather={data.weather} source={data.sources.weather} nowMs={nowMs} />
            <QuakeCard quakes={data.earthquakes} nowMs={nowMs} />
          </div>
        )}
      </div>
    </details>
  )
}

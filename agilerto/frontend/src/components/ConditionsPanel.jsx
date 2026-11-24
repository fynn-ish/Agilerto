import { useState } from 'react'
import { triggerRefresh } from '../api'
import { describeStatus } from '../status'
import AdvisoryCard from './AdvisoryCard'
import NewsCard from './NewsCard'
import QuakeCard from './QuakeCard'
import StatusBadge from './StatusBadge'
import WeatherCard from './WeatherCard'

// Online/Offline status, then advisories, weather, earthquakes and news. Lives in its own tab beside the map.
export default function ConditionsPanel({ dash }) {
  const { data, fromCache, nowMs, reload } = dash
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  const canRefresh = data && data.online && !fromCache
  async function refresh() {
    setBusy(true)
    setNote('')
    try {
      const r = await triggerRefresh()
      const groups = ['weather', 'earthquakes', 'advisories', 'news'].filter((g) => r[g])
      if (r.status === 'cooldown') setNote(`Please wait ${r.retry_in_seconds} s before refreshing again.`)
      else if (r.status === 'offline') setNote('No internet connection right now. Showing saved data.')
      else if (r.status === 'busy') setNote('A refresh is already running.')
      else if (groups.some((g) => r[g].ok === false)) setNote('Some data could not be updated. Saved data is kept. See "Source status" in each card.')
      else setNote('Updated.')
      reload()
    } catch {
      setNote('Could not reach the server.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="Current conditions" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-white p-3">
        <StatusBadge dash={dash} />
        {canRefresh && (
          <button
            type="button" onClick={refresh} disabled={busy}
            className="min-h-11 rounded-md border-2 border-brand px-4 font-bold text-brand hover:bg-brand hover:text-white disabled:opacity-60"
          >
            {busy ? 'Refreshing…' : 'Refresh now'}
          </button>
        )}
      </div>
      {note && <p role="status" className="text-sm font-bold">{note}</p>}

      {data && (
        <>
          {/* Older cached copies (saved before advisories existed) do not have these sections */}
          {data.advisories && <AdvisoryCard advisories={data.advisories} nowMs={nowMs} />}
          <WeatherCard weather={data.weather} source={data.sources.weather} nowMs={nowMs} />
          <QuakeCard quakes={data.earthquakes} nowMs={nowMs} />
          {data.news && <NewsCard news={data.news} nowMs={nowMs} />}
        </>
      )}
    </section>
  )
}

// Alerts that deserve to be seen without opening a tab: Orange, Red, or an active PAGASA bulletin.
export function importantAlerts(dash) {
  return (dash.data?.advisories?.items ?? []).filter((a) => ['Red', 'Orange', 'Bulletin'].includes(a.severity))
}

export function alertCount(dash) {
  return (dash.data?.advisories?.items ?? []).filter((a) => a.category !== 'status').length
}
export { describeStatus }

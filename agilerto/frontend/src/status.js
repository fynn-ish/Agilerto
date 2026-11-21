import { clock, timeAgo } from './time'

const latest = (a, b) => [a, b].filter(Boolean).sort().pop() ?? null

// One place that decides what the Online/Offline badge says, used by the conditions panel and the chat.
export function describeStatus({ status, data, fromCache, savedAt, nowMs }) {
  if (status === 'loading') return { tone: 'amber', label: 'Checking', detail: 'Loading saved conditions…', lastSync: null }
  if (status === 'error' || !data) {
    return { tone: 'amber', label: 'Offline', detail: 'Conditions could not be loaded. Check that the backend is running.', lastSync: null }
  }
  const lastSync = latest(data.sources.weather.last_success_at, data.sources.earthquakes.last_success_at)
  if (fromCache) {
    return { tone: 'amber', label: 'Server unreachable', detail: `Showing a copy saved on this device (${clock(savedAt)}).`, lastSync }
  }
  if (data.online) {
    return {
      tone: 'green', label: 'Online', lastSync,
      detail: lastSync ? `Data refreshed ${timeAgo(lastSync, nowMs)}.` : 'No live data downloaded yet. Tap Refresh.',
    }
  }
  return {
    tone: 'amber', label: 'Offline', lastSync,
    detail: lastSync
      ? `Showing data saved ${clock(lastSync)} (${timeAgo(lastSync, nowMs)}).`
      : 'No live data saved yet. Connect to the internet once to download it.',
  }
}

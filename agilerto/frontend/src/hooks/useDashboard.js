import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchDashboard } from '../api'

// Loads the dashboard for a location, re-checks every minute, and keeps a "now" clock
// (corrected to the server's clock) so "updated 4 min ago" stays right.
export function useDashboard(location) {
  const [state, setState] = useState({ status: 'loading', data: null, fromCache: false, savedAt: null })
  const [reloadKey, setReloadKey] = useState(0)
  const [now, setNow] = useState(Date.now())
  const offset = useRef(0)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchDashboard({ lat: location.lat, lng: location.lng }, ctrl.signal)
      .then(({ data, fromCache, savedAt }) => {
        if (!fromCache) offset.current = Date.parse(data.server_time) - Date.now()
        setState({ status: 'ready', data, fromCache, savedAt: savedAt ?? null })
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setState({ status: 'error', data: null, fromCache: false, savedAt: null })
      })
    return () => ctrl.abort()
  }, [location.lat, location.lng, reloadKey])

  useEffect(() => {
    const poll = setInterval(() => setReloadKey((k) => k + 1), 60_000)
    const tick = setInterval(() => setNow(Date.now()), 20_000)
    return () => { clearInterval(poll); clearInterval(tick) }
  }, [])

  const reload = useCallback(() => setReloadKey((k) => k + 1), [])
  return { ...state, nowMs: now + offset.current, reload }
}

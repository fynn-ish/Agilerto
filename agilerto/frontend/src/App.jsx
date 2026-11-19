import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchFacilities } from './api'
import { DEFAULT_LOCATION, FACILITY_TYPES } from './constants'
import HotlineBar from './components/HotlineBar'
import LocationControls from './components/LocationControls'
import TypeFilter from './components/TypeFilter'
import FacilityMap from './components/FacilityMap'
import FacilityList from './components/FacilityList'
import ConditionsPanel from './components/ConditionsPanel'
import { useDashboard } from './hooks/useDashboard'

function loadSavedLocation() {
  try {
    const s = JSON.parse(localStorage.getItem('location'))
    if (s && Number.isFinite(s.lat) && Number.isFinite(s.lng)) return s
  } catch { /* ignore */ }
  return DEFAULT_LOCATION
}

export default function App() {
  const [location, setLocation] = useState(loadSavedLocation)
  const [radius, setRadius] = useState(10)
  const [active, setActive] = useState(() => new Set(FACILITY_TYPES.map((t) => t.key)))
  const [selectedId, setSelectedId] = useState(null)
  const [state, setState] = useState({ status: 'loading', facilities: [], fromCache: false, savedAt: null })
  const dash = useDashboard(location)

  const updateLocation = useCallback((loc) => {
    setLocation(loc)
    setSelectedId(null)
    try { localStorage.setItem('location', JSON.stringify(loc)) } catch { /* ignore */ }
  }, [])

  // Fetch everything in range once; type filters are applied locally so they're instant.
  useEffect(() => {
    const ctrl = new AbortController()
    setState((s) => ({ ...s, status: 'loading' }))
    fetchFacilities({ lat: location.lat, lng: location.lng, radius }, ctrl.signal)
      .then(({ data, fromCache, savedAt }) =>
        setState({ status: 'ready', facilities: data.facilities, fromCache, savedAt }))
      .catch((err) => {
        if (err.name !== 'AbortError') setState({ status: 'error', facilities: [], fromCache: false, savedAt: null })
      })
    return () => ctrl.abort()
  }, [location.lat, location.lng, radius])

  const counts = useMemo(() => {
    const c = {}
    state.facilities.forEach((f) => { c[f.type] = (c[f.type] || 0) + 1 })
    return c
  }, [state.facilities])

  const visible = useMemo(
    () => state.facilities.filter((f) => active.has(f.type)),
    [state.facilities, active],
  )
  const hasUnverified = visible.some((f) => !f.verified)

  const toggleType = (key) =>
    setActive((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })

  return (
    <div className="flex min-h-full flex-col">
      <HotlineBar />

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-4 px-4 py-4">
        <h1 className="text-2xl font-bold">Help near you</h1>

        <LocationControls location={location} radius={radius} onLocate={updateLocation} onRadius={setRadius} />
        <TypeFilter active={active} counts={counts} onToggle={toggleType} />

        {state.fromCache && (
          <p role="status" className="rounded-md bg-amber-100 p-3 text-amber-950">
            Can't reach the server. Showing the last saved results from {new Date(state.savedAt).toLocaleString()}.
          </p>
        )}
        {state.status === 'error' && (
          <p role="alert" className="rounded-md bg-red-100 p-3 text-red-950">
            Facilities could not be loaded and no saved copy exists for this area. Check that the
            backend is running, then reload.
          </p>
        )}
        {hasUnverified && (
          <p className="rounded-md bg-amber-100 p-3 text-amber-950">
            Some places below are unverified. Call ahead or confirm with your local DRRMO before travelling.
          </p>
        )}

        <ConditionsPanel dash={dash} />

        <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div className="h-[55vh] lg:sticky lg:top-16 lg:h-[calc(100vh-5rem)]">
            <FacilityMap
              center={location}
              radiusKm={radius}
              facilities={visible}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onPick={({ lat, lng }) => updateLocation({ lat, lng, label: 'the point you picked', source: 'map' })}
            />
          </div>

          <section aria-label="Facility list" aria-busy={state.status === 'loading'}>
            <h2 className="mb-2 text-lg font-bold">
              {visible.length} {visible.length === 1 ? 'place' : 'places'} within {radius} km, nearest first
            </h2>
            <FacilityList facilities={visible} selectedId={selectedId} onSelect={setSelectedId} />
          </section>
        </div>
      </main>

      <footer className="border-t border-line px-4 py-3 text-center text-sm text-muted">
        Facility data is stored on this system and works without internet. Map background needs a connection until
        offline tiles are installed.
      </footer>
    </div>
  )
}

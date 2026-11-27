import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchFacilities, fetchTilesInfo } from './api'
import { DEFAULT_LOCATION, FACILITY_TYPES } from './constants'
import HotlineBar from './components/HotlineBar'
import LocationControls from './components/LocationControls'
import TypeFilter from './components/TypeFilter'
import FacilityMap from './components/FacilityMap'
import FacilityList from './components/FacilityList'
import ConditionsPanel, { alertCount, importantAlerts } from './components/ConditionsPanel'
import ChatPanel from './components/ChatPanel'
import MapStatus from './components/MapStatus'
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
  const [tab, setTab] = useState('places')          // 'places' | 'ask' | 'conditions'
  const [tiles, setTiles] = useState(null)              // null while checking, then { mode: 'local' | 'online', info }
  const [cited, setCited] = useState([])            // facilities cited by the assistant's last answer

  const updateLocation = useCallback((loc) => {
    setLocation(loc)
    setSelectedId(null)
    try { localStorage.setItem('location', JSON.stringify(loc)) } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    fetchTilesInfo().then((info) => setTiles(info?.usable ? { mode: 'local', info } : { mode: 'online', info }))
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
  const important = importantAlerts(dash)
  const alerts = alertCount(dash)

  // Cited places are always drawn on the map, even if they are outside the radius or filtered out of the list.
  const citedIds = useMemo(() => new Set(cited.map((f) => f.id)), [cited])
  const mapFacilities = useMemo(() => {
    const inList = new Set(visible.map((f) => f.id))
    return [...visible, ...cited.filter((f) => !inList.has(f.id))]
  }, [visible, cited])

  const showOnMap = useCallback((facility) => {
    setSelectedId(facility.id)
    document.getElementById('map-panel')?.scrollIntoView({ block: 'nearest' })
  }, [])

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

        {important.length > 0 && (
          <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border-2 border-alarm bg-red-50 p-3">
            <p className="min-w-0 flex-1">
              <strong>{important.length === 1 ? 'Active alert' : `${important.length} active alerts`}:</strong>{' '}
              {important[0].severity === 'Bulletin'
                ? important[0].title
                : `${important[0].severity} alert from ${important[0].source}${important[0].source === 'GDACS' ? ' (automated)' : ''}: ${important[0].title}`}
              {important.length > 1 && ' and more'}
            </p>
            <button type="button" onClick={() => setTab('conditions')}
              className="min-h-11 rounded-md border-2 border-alarm px-4 font-bold text-alarm hover:bg-alarm hover:text-white">
              View advisories
            </button>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div id="map-panel" className="flex h-[55vh] flex-col lg:sticky lg:top-16 lg:h-[calc(100vh-5rem)]">
            <div className="min-h-0 flex-1">
              <FacilityMap
                center={location}
                radiusKm={radius}
                facilities={mapFacilities}
                selectedId={selectedId}
                citedIds={citedIds}
                tiles={tiles}
                onSelect={setSelectedId}
                onPick={({ lat, lng }) => updateLocation({ lat, lng, label: 'the point you picked', source: 'map' })}
              />
            </div>
            <MapStatus tiles={tiles} center={location} />
          </div>

          <div>
            <div role="tablist" aria-label="Panels" className="mb-3 grid grid-cols-3 gap-2">
              {[['places', 'Nearby places'], ['ask', 'Ask the assistant'], ['conditions', alerts ? `Conditions (${alerts})` : 'Conditions']].map(([key, label]) => (
                <button
                  key={key} type="button" role="tab" id={`tab-${key}`} aria-selected={tab === key} aria-controls={`panel-${key}`}
                  onClick={() => setTab(key)}
                  className={`min-h-11 rounded-md border-2 px-2 text-sm font-bold sm:text-base ${tab === key ? 'border-brand bg-brand text-white' : 'border-line bg-white'}`}
                >
                  {label}
                </button>
              ))}
            </div>

            <section role="tabpanel" id="panel-places" aria-labelledby="tab-places" hidden={tab !== 'places'} aria-busy={state.status === 'loading'}>
              <h2 className="mb-2 text-lg font-bold">
                {visible.length} {visible.length === 1 ? 'place' : 'places'} within {radius} km, nearest first
              </h2>
              <FacilityList facilities={visible} selectedId={selectedId} onSelect={setSelectedId} />
            </section>

            <div role="tabpanel" id="panel-conditions" aria-labelledby="tab-conditions" hidden={tab !== 'conditions'}>
              <ConditionsPanel dash={dash} />
            </div>

            {/* Stays mounted while hidden so the conversation is not lost when switching tabs */}
            <div role="tabpanel" id="panel-ask" aria-labelledby="tab-ask" hidden={tab !== 'ask'}>
              <ChatPanel location={location} dash={dash} onCite={setCited} onSelectFacility={showOnMap} />
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-line px-4 py-3 text-center text-sm text-muted">
        Facility data is stored on this system and works without internet. Map background needs a connection until
        offline tiles are installed.
      </footer>
    </div>
  )
}

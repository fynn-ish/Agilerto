// One line under the map saying which map is in use, and why, so a blank map is never a mystery.
export default function MapStatus({ tiles, center }) {
  if (!tiles) return <p className="pt-1 text-xs text-muted">Checking the map…</p>
  const { mode, info } = tiles

  if (mode === 'local') {
    const [w, s, e, n] = info.bounds
    const inside = center.lng >= w && center.lng <= e && center.lat >= s && center.lat <= n
    return (
      <p className="pt-1 text-xs text-muted" role="status">
        <strong className="text-ink">Offline map</strong> ({info.name || info.file}, zoom {info.minzoom} to {info.maxzoom}). Works without internet.
        {!inside && <strong className="text-amber-900"> This location is outside the offline map area. Markers still work.</strong>}
      </p>
    )
  }
  return (
    <p className="pt-1 text-xs text-muted" role="status">
      <strong className="text-ink">Online map</strong>. The background needs internet and will be blank offline.
      {info?.reason && <> {info.available ? 'The offline tile file was not used: ' : ''}{info.reason}</>}
    </p>
  )
}

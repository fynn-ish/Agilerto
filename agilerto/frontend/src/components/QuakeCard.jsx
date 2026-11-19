import { timeAgo } from '../time'
import Freshness from './Freshness'

const SHOWN = 5

export default function QuakeCard({ quakes, nowMs }) {
  const { has_data, count, items, radius_km, days, min_magnitude } = quakes
  return (
    <article className="rounded-md border border-line bg-white p-4">
      <h3 className="text-lg font-bold">Earthquakes</h3>
      <p className="text-sm text-muted">
        Magnitude {min_magnitude}+ within {radius_km} km, last {days} days
      </p>

      {!has_data ? (
        <p className="pt-2">No earthquake data has been downloaded yet. Connect to the internet once, then tap Refresh.</p>
      ) : count === 0 ? (
        <p className="pt-2">No earthquakes of this size were recorded nearby in this period.</p>
      ) : (
        <>
          <p className="pt-2 font-bold">{count} recorded</p>
          <ul className="mt-1 divide-y divide-line">
            {items.slice(0, SHOWN).map((q) => (
              <li key={q.ext_id} className="flex gap-3 py-2">
                <span className="h-fit shrink-0 rounded border-2 border-ink px-2 py-0.5 font-bold tabular-nums">
                  M{Number(q.magnitude).toFixed(1)}
                </span>
                <div className="min-w-0 text-sm">
                  <p className="font-bold">{q.place || 'Location not given'}</p>
                  <p className="text-muted tabular-nums">
                    {q.distance_km} km from you
                    {q.depth_km != null && <> · depth {Math.round(q.depth_km)} km</>}
                    {' · '}{timeAgo(q.occurred_at, nowMs)}
                    {q.url && <> · <a className="text-brand underline underline-offset-2" href={q.url} target="_blank" rel="noopener noreferrer">USGS page</a></>}
                  </p>
                </div>
              </li>
            ))}
          </ul>
          {count > SHOWN && <p className="pt-1 text-sm text-muted">Showing the {SHOWN} most recent of {count}.</p>}
        </>
      )}

      <Freshness fetchedAt={quakes.fetched_at} stale={quakes.stale && has_data} nowMs={nowMs} what="earthquake" />
      <p className="pt-1 text-xs text-muted">
        Source: USGS. Small local earthquakes can appear late or be missing. PHIVOLCS is the official Philippine source.
      </p>
    </article>
  )
}

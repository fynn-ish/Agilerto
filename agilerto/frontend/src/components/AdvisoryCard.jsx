import { clock, timeAgo } from '../time'
import ExternalLink from './ExternalLink'
import Freshness from './Freshness'
import SourceHealth from './SourceHealth'

const CATEGORY = { tropical_cyclone: 'Tropical cyclone', flood: 'Flood', volcano: 'Volcano', status: 'Status' }
const BORDER = { Red: 'border-alarm', Bulletin: 'border-alarm', Orange: 'border-fire', Green: 'border-evac', None: 'border-line' }

// The words carry the meaning, so it does not depend on color.
function levelLabel(a) {
  if (a.severity === 'Bulletin') return 'PAGASA bulletin'
  if (a.severity === 'None') return 'Status'
  return `${a.severity} alert`
}

export default function AdvisoryCard({ advisories, nowMs }) {
  const { items, has_data: hasData, stale, fetched_at: fetchedAt, sources } = advisories
  const alerts = items.filter((a) => a.category !== 'status')
  const statuses = items.filter((a) => a.category === 'status')

  return (
    <article className="rounded-md border border-line bg-white p-4">
      <h3 className="text-lg font-bold">Advisories</h3>
      <p className="text-sm text-muted">PAGASA bulletin status and automated GDACS alerts for the Philippines.</p>

      {!hasData ? (
        <p className="pt-2">
          No advisory data has been downloaded yet. Connect to the internet once, then tap Refresh. Until then, check
          PAGASA, PHIVOLCS, and your local DRRMO directly.
        </p>
      ) : (
        <>
          {statuses.map((a) => (
            <div key={a.title} className="mt-2 rounded border-l-4 border-line bg-paper p-2 text-sm">
              <p><strong>{a.source}:</strong> {a.title.replace(/^PAGASA bulletin page: /, '')}</p>
              <p className="text-muted">Checked {timeAgo(a.fetched_at, nowMs)}. {a.body}</p>
              <ExternalLink href={a.url}>Open the PAGASA page</ExternalLink>
            </div>
          ))}

          {alerts.length === 0 ? (
            <p className="pt-2 text-sm">No active GDACS alerts for the Philippines are saved.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {alerts.map((a) => (
                <li key={a.title} className={`rounded border-l-4 bg-white p-2 ${BORDER[a.severity] || 'border-line'} shadow-[inset_0_0_0_1px_var(--color-line)]`}>
                  <p>
                    <strong className="rounded border-2 border-ink px-1.5 text-sm">{levelLabel(a)}</strong>{' '}
                    <span className="text-sm text-muted">{CATEGORY[a.category] || 'Event'} · {a.source}</span>
                  </p>
                  <p className="pt-1 font-bold">{a.title}</p>
                  <p className="text-sm text-muted tabular-nums">
                    {a.area && <>{a.area} · </>}
                    {a.distance_km != null && <>centre about {a.distance_km} km from you · </>}
                    {a.issued_at && <>updated {clock(a.issued_at)}</>}
                  </p>
                  <ExternalLink href={a.url} className="text-sm">Read at source</ExternalLink>
                </li>
              ))}
            </ul>
          )}

          <Freshness fetchedAt={fetchedAt} stale={stale} nowMs={nowMs} what="advisory" />
        </>
      )}

      <p className="pt-2 text-xs text-muted">
        GDACS alerts are automated (UN and European Commission) and are not official Philippine warnings. Having no alert
        here does not mean there is no warning. Always check PAGASA, PHIVOLCS, NDRRMC, and your local DRRMO. GDACS data: CC BY 4.0.
      </p>
      <SourceHealth sources={sources} nowMs={nowMs} />
    </article>
  )
}

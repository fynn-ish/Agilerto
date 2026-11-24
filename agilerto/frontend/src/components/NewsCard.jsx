import { timeAgo } from '../time'
import ExternalLink from './ExternalLink'
import Freshness from './Freshness'
import SourceHealth from './SourceHealth'

export default function NewsCard({ news, nowMs }) {
  const { items, total, days, has_data: hasData, stale, fetched_at: fetchedAt, sources } = news
  return (
    <article className="rounded-md border border-line bg-white p-4">
      <h3 className="text-lg font-bold">News</h3>
      <p className="text-sm text-muted">Hazard-related headlines from the last {days} days. Stories about your area come first.</p>

      {!hasData ? (
        <p className="pt-2">No headlines have been downloaded yet. Connect to the internet once, then tap Refresh.</p>
      ) : items.length === 0 ? (
        <p className="pt-2">No hazard-related headlines were saved for the last {days} days.</p>
      ) : (
        <>
          <ul className="mt-2 divide-y divide-line">
            {items.map((n) => (
              <li key={n.url} className="py-2">
                <p className="font-bold leading-snug">
                  <ExternalLink href={n.url} className="no-underline hover:underline">{n.title}</ExternalLink>
                </p>
                {n.summary && <p className="line-clamp-2 text-sm">{n.summary}</p>}
                <p className="text-sm text-muted">
                  {n.local && <strong className="mr-1 rounded border border-ink px-1 text-ink">Your area</strong>}
                  {n.source} · {n.published_at ? timeAgo(n.published_at, nowMs) : 'date not given'}
                </p>
              </li>
            ))}
          </ul>
          {total > items.length && <p className="text-sm text-muted">Showing {items.length} of {total} recent headlines.</p>}
        </>
      )}

      <Freshness fetchedAt={fetchedAt} stale={stale && hasData} nowMs={nowMs} what="news" />
      <p className="pt-1 text-xs text-muted">
        Headlines come from news outlets and have not been verified by this system. They report what happened, and are
        not instructions. Links need internet.
      </p>
      <SourceHealth sources={sources} nowMs={nowMs} />
    </article>
  )
}

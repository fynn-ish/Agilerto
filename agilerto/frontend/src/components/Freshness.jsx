import { clock, timeAgo } from '../time'

// Every live-data card shows when it was last updated and warns when it is old.
export default function Freshness({ fetchedAt, stale, nowMs, what }) {
  return (
    <div className="space-y-1 pt-2">
      <p className="text-sm text-muted">
        Updated <strong className="text-ink">{timeAgo(fetchedAt, nowMs)}</strong>
        {fetchedAt && <> ({clock(fetchedAt)})</>}
      </p>
      {stale && (
        <p role="status" className="rounded bg-amber-100 px-2 py-1 text-sm text-amber-950">
          This {what} data is old. Conditions may have changed. Check official sources.
        </p>
      )}
    </div>
  )
}

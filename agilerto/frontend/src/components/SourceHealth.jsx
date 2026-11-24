import { clock, timeAgo } from '../time'

// One line per data source, so a broken source shows as "unavailable" instead of silently looking fine.
export default function SourceHealth({ sources, nowMs }) {
  if (!sources?.length) return null
  const anyProblem = sources.some((s) => s.failing || s.note)
  return (
    <details className="pt-2 text-sm" open={anyProblem}>
      <summary className="min-h-8 cursor-pointer font-bold">
        Source status{anyProblem && ' (a problem was found)'}
      </summary>
      <ul className="space-y-1 pt-1">
        {sources.map((s) => (
          <li key={s.name}>
            <strong>{s.name}:</strong>{' '}
            {!s.checked ? 'not checked yet'
              : s.failing ? <span className="font-bold text-amber-900">unavailable ({s.last_error})</span>
              : <>updated {timeAgo(s.last_success_at, nowMs)} ({clock(s.last_success_at)})</>}
            {s.failing && s.last_success_at && <> · last worked {timeAgo(s.last_success_at, nowMs)}</>}
            {s.note && <span className="text-muted"> · part of it failed: {s.note}</span>}
          </li>
        ))}
      </ul>
    </details>
  )
}

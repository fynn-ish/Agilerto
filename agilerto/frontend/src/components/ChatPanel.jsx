import { useEffect, useRef, useState } from 'react'
import { askChat, fetchAiStatus } from '../api'
import { clock } from '../time'
import ExternalLink from './ExternalLink'
import StatusBadge from './StatusBadge'

const SUGGESTIONS = [
  'Where is the nearest hospital?',
  'Nearest evacuation center',
  "What's the weather now?",
  'Recent earthquakes near me',
  'What should I do during an earthquake?',
  'Any advisories or warnings?',
  'Latest news about the typhoon',
  'Emergency hotlines',
  'Saan ang pinakamalapit na ospital?',
]

const KIND_LABEL = { facility: 'Place', hotline: 'Hotline', guide: 'Safety guide', weather: 'Weather', quake: 'Earthquake', advisory: 'Advisory', news: 'News' }
const CITE_SPLIT = /(\[\d+(?:\s*,\s*\d+)*\])/g
const CITE_ONE = /^\[(\d+(?:\s*,\s*\d+)*)\]$/

function AiBadge({ ai }) {
  if (!ai) return <span className="text-sm text-muted">Checking the AI…</span>
  const ready = ai.running && ai.model_installed
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span aria-hidden="true" className={`inline-block h-3 w-3 rounded-full ${ready ? 'bg-evac' : 'bg-amber-600'}`} />
      <span className="font-bold">{ready ? `AI ready` : 'AI not ready'}</span>
      <span className="text-muted">
        {ready ? ai.model : ai.running ? ai.message : 'Start Ollama. Answers will show saved records only.'}
      </span>
    </span>
  )
}

function Hotlines({ numbers, calm = false }) {
  if (!numbers?.length) return null
  return (
    <ul className="flex flex-wrap gap-2 pt-2">
      {numbers.map((n) => (
        <li key={`${n.agency}-${n.number}`}>
          <a
            href={`tel:${n.number.replace(/[^\d+]/g, '')}`}
            className={`inline-flex min-h-11 items-center gap-2 rounded-md border-2 px-3 font-bold ${calm ? 'border-brand text-brand hover:bg-brand hover:text-white' : 'border-alarm text-alarm hover:bg-alarm hover:text-white'}`}
          >
            <span className="text-lg tabular-nums">{n.number}</span>
            <span className="text-sm font-normal">{n.agency}</span>
          </a>
        </li>
      ))}
    </ul>
  )
}

// Replaces [1] and [1, 2] in the answer with buttons that jump to the matching source.
function AnswerText({ text, onCite }) {
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {text.split(CITE_SPLIT).map((part, i) => {
        const m = part.match(CITE_ONE)
        if (!m) return <span key={i}>{part}</span>
        return m[1].split(',').map((x) => {
          const n = Number(x.trim())
          return (
            <button
              key={`${i}-${n}`}
              type="button"
              onClick={() => onCite(n)}
              aria-label={`Show source ${n}`}
              className="mx-0.5 rounded border border-line bg-paper px-1 text-sm font-bold text-brand hover:bg-brand hover:text-white"
            >
              [{n}]
            </button>
          )
        })
      })}
    </p>
  )
}

const OUTCOME_TITLE = {
  emergency: 'Emergency',
  distress: 'You are not alone',
  refused: 'Something I can’t answer',
  ai_unavailable: 'Showing saved records (the AI is not running)',
  fallback: 'Showing saved records (answer could not be verified)',
  no_sources: 'Nothing found in saved data',
  no_advisories: 'No saved advisory (this is not the same as no warning)',
  not_in_sources: 'Not in saved data',
  busy: 'Please wait',
}

function AssistantMessage({ msg, onSelectFacility }) {
  const r = msg.result
  const [active, setActive] = useState(null)
  const emergency = r.outcome === 'emergency'
  const flagged = ['ai_unavailable', 'fallback', 'busy'].includes(r.outcome)
  const distress = r.outcome === 'distress'

  function cite(n) {
    setActive(n)
    const c = r.citations.find((x) => x.n === n)
    if (c?.facility) onSelectFacility(c.facility)
  }

  const box = emergency
    ? 'border-alarm bg-red-50'
    : distress ? 'border-sky-400 bg-sky-50'
    : flagged ? 'border-amber-500 bg-amber-50' : 'border-line bg-white'

  return (
    <div data-assistant className={`rounded-md border-2 p-3 ${box}`}>
      {OUTCOME_TITLE[r.outcome] && <p className={`pb-1 text-sm font-bold ${emergency ? 'text-alarm' : ''}`}>{OUTCOME_TITLE[r.outcome]}</p>}
      <AnswerText text={r.answer} onCite={cite} />

      {(emergency || distress || ['refused', 'no_sources', 'not_in_sources', 'no_advisories'].includes(r.outcome)) && (
        <Hotlines numbers={r.emergency_numbers} calm={distress} />
      )}

      {r.ai_message && r.outcome === 'ai_unavailable' && <p className="pt-2 text-sm text-muted">{r.ai_message}</p>}

      {r.notices.map((n) => (
        <p key={n.text} role="status" className={`mt-2 rounded px-2 py-1 text-sm ${n.level === 'warn' ? 'bg-amber-100 text-amber-950' : 'bg-paper text-muted'}`}>
          {n.text}
        </p>
      ))}

      {r.citations.length > 0 && (
        <details open className="mt-3">
          <summary className="min-h-8 cursor-pointer text-sm font-bold">Sources ({r.citations.length})</summary>
          <ul className="space-y-1.5 pt-1">
            {r.citations.map((c) => (
              <li key={c.n}>
                <button
                  type="button"
                  onClick={() => cite(c.n)}
                  aria-pressed={active === c.n}
                  className={`block w-full rounded-md border bg-white p-2 text-left text-sm ${active === c.n ? 'border-ink border-2' : 'border-line'}`}
                >
                  <span className="font-bold">[{c.n}] {c.title}</span>
                  <span className="block text-muted">
                    {KIND_LABEL[c.kind]} · {c.source || 'Saved data'} ·{' '}
                    {c.as_of ? `as of ${clock(c.as_of)}` : 'saved reference data'}
                    {c.distance_km != null && <> · {c.distance_km} km from you</>}
                    {c.verified === false && <> · <span className="font-bold text-amber-900">Unverified</span></>}
                  </span>
                  {c.facility && <span className="font-bold text-brand underline underline-offset-2">Show on map</span>}
                </button>
                {c.url && <p className="px-2 pt-0.5 text-sm"><ExternalLink href={c.url}>Read at source</ExternalLink> <span className="text-muted">(needs internet)</span></p>}
              </li>
            ))}
          </ul>
        </details>
      )}

      <p className="pt-2 text-xs text-muted">
        {r.as_of ? `Live data as of ${clock(r.as_of)}` : 'Based on saved reference data'}
        {' · '}{r.online ? 'Online' : 'Offline'}
        {r.model && <> · {r.model}</>}
        {' · '}{(r.elapsed_ms / 1000).toFixed(1)} s
      </p>
    </div>
  )
}

export default function ChatPanel({ location, dash, onCite, onSelectFacility }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [ai, setAi] = useState(null)
  const abortRef = useRef(null)
  const scroller = useRef(null)

  useEffect(() => {
    let alive = true
    const check = () => fetchAiStatus().then((s) => alive && setAi(s ?? { running: false, model_installed: false, model: '', message: 'Cannot reach the server.' }))
    check()
    const id = setInterval(check, 30_000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  useEffect(() => {
    if (!loading) return undefined
    setElapsed(0)
    const id = setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => clearInterval(id)
  }, [loading])

  useEffect(() => {
    const box = scroller.current
    if (!box) return
    const last = messages[messages.length - 1]
    if (last?.role === 'assistant' && !loading) {
      // A new answer: show its first line (for emergencies that is "Call 911"), not its last.
      const cards = box.querySelectorAll('[data-assistant]')
      const el = cards[cards.length - 1]
      if (el) box.scrollTo({ top: el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop - 4 })
    } else {
      box.scrollTo({ top: box.scrollHeight })
    }
  }, [messages, loading])

  async function send(text) {
    const question = text.trim()
    if (!question || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: question }])
    setLoading(true)
    const ctrl = new AbortController()
    abortRef.current = ctrl
    const timeout = setTimeout(() => ctrl.abort('timeout'), 200_000)
    try {
      const result = await askChat({ question, lat: location.lat, lng: location.lng }, ctrl.signal)
      setMessages((m) => [...m, { role: 'assistant', result }])
      onCite(result.citations.filter((c) => c.facility).map((c) => c.facility))
      fetchAiStatus().then((s) => s && setAi(s))
    } catch (err) {
      const stopped = err.name === 'AbortError'
      const slowDown = err.status === 429
      setMessages((m) => [...m, {
        role: 'assistant',
        error: slowDown
          ? `Many questions were sent in a short time. Please wait about ${err.retryAfter ?? 60} seconds and try again. If this is an emergency, call 911.`
          : stopped ? 'Stopped. The assistant took too long or you cancelled.' : 'Could not reach the assistant. Check that the backend is running.',
      }])
    } finally {
      clearTimeout(timeout)
      setLoading(false)
    }
  }

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  return (
    <section aria-label="Ask the assistant" className="space-y-3">
      <div className="space-y-1 rounded-md border border-line bg-white p-3">
        <StatusBadge dash={dash} />
        <AiBadge ai={ai} />
        <p className="text-sm text-muted">Answering for <strong className="text-ink">{location.label}</strong>.</p>
      </div>

      <div ref={scroller} role="log" aria-live="polite" aria-label="Conversation" className="max-h-[55vh] min-h-40 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="space-y-2 rounded-md border border-dashed border-line p-3">
            <p>Ask about nearby help, the weather, recent earthquakes, hotlines, or safety tips. English, Tagalog, and Taglish all work.</p>
            <ul className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <li key={s}>
                  <button type="button" onClick={() => send(s)} disabled={loading}
                    className="min-h-11 rounded-md border border-brand px-3 text-left text-brand hover:bg-brand hover:text-white disabled:opacity-60">
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === 'user' ? (
            <div key={i} className="ml-8 rounded-md bg-brand p-3 text-white"><p className="whitespace-pre-wrap">{m.text}</p></div>
          ) : m.error ? (
            <p key={i} data-assistant role="alert" className="rounded-md border-2 border-red-300 bg-red-50 p-3 text-red-950">{m.error}</p>
          ) : (
            <AssistantMessage key={i} msg={m} onSelectFacility={onSelectFacility} />
          ),
        )}

        {loading && (
          <div role="status" className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-white p-3">
            <span>Searching saved data and asking the local AI… {elapsed} s</span>
            <button type="button" onClick={() => abortRef.current?.abort()} className="min-h-11 rounded-md border border-line px-3 font-bold">Cancel</button>
            {elapsed > 20 && <span className="w-full text-sm text-muted">The first answer can take a while while the model loads.</span>}
          </div>
        )}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(input) }} className="space-y-2">
        <label htmlFor="chat-input" className="sr-only">Your question</label>
        <textarea
          id="chat-input" rows={2} maxLength={500} value={input}
          onChange={(e) => setInput(e.target.value)} onKeyDown={onKey}
          placeholder="Type your question…"
          className="w-full rounded-md border border-line bg-white p-3 text-base"
        />
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted">Answers use only the saved sources shown. This assistant does not predict disasters or tell you whether to evacuate.</p>
          <button type="submit" disabled={loading || !input.trim()}
            className="min-h-11 shrink-0 rounded-md bg-brand px-5 font-bold text-white hover:bg-brand-dark disabled:opacity-50">
            Ask
          </button>
        </div>
      </form>
    </section>
  )
}

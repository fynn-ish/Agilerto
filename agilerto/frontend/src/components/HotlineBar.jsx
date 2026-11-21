import { useEffect, useState } from 'react'
import { fetchHotlines } from '../api'

// Shown even if the backend is unreachable, so a call-for-help path is always on screen.
const FALLBACK = [{ agency: 'National Emergency Hotline', number: '911' }]

export default function HotlineBar() {
  const [numbers, setNumbers] = useState(FALLBACK)

  useEffect(() => {
    fetchHotlines().then((n) => n?.length && setNumbers(n))
  }, [])

  const callable = numbers.filter((n) => /\d/.test(n.number))

  return (
    <>
      <header className="sticky top-0 z-[2000] bg-alarm text-white">
        <nav aria-label="Emergency hotlines" className="mx-auto max-w-7xl overflow-x-auto px-4 py-1.5">
          <ul className="flex items-center gap-5">
            <li className="shrink-0 text-sm font-bold">Call for help</li>
            {callable.map((n) => (
              <li key={n.agency} className="shrink-0">
                <a
                  href={`tel:${n.number.replace(/[^\d+]/g, '')}`}
                  className="block leading-tight underline decoration-white/40 underline-offset-4 hover:decoration-white"
                >
                  <strong className="block text-lg tabular-nums">{n.number}</strong>
                  <span className="block text-xs">{n.agency}</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <p className="bg-alarm/10 px-4 py-1.5 text-center text-sm text-ink">
        This page shares information only. It does not predict disasters or tell you whether to
        evacuate. Follow your local authorities.
      </p>
    </>
  )
}

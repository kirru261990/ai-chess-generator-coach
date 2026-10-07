import { useEffect, useState } from 'react'
import { cards, engineText, type BlindSpotsResponse } from './spotCards'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export default function BlindSpots() {
  const [data, setData] = useState<BlindSpotsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API}/blind-spots/baseline`)
      .then(async (res) => {
        const body = await res.json()
        if (!res.ok) throw new Error(body.message ?? `Request failed (${res.status})`)
        setData(body as BlindSpotsResponse)
      })
      .catch((e: Error) => setError(e.message || 'Cannot reach the API. Is the backend running on port 8000?'))
  }, [])

  if (error)
    return (
      <p role="alert" className="error">
        {error}
      </p>
    )
  if (!data) return <p>Loading…</p>

  const entries = Object.entries(data.results.by_time_control)
  return (
    <section className="spots">
      <h2>Your blind spots</h2>
      <p className="note">
        What happened in your 100 baseline games (the last 100 before coaching started), one list for each time
        control. They are never mixed together.
      </p>
      <div className="columns">
        {entries.map(([name, tc]) => (
          <div key={name} className="column">
            <h3>
              {name} <span className="sub">{tc.games} games · {tc.user_moves} of your moves</span>
            </h3>
            {cards(tc).map((c) => (
              <article key={c.key} className="card">
                <div className="card-top">
                  <strong>{c.title}</strong>
                  <span className={`chip ${c.badgeKind}`}>{c.badge}</span>
                </div>
                <p className="what">{c.what}</p>
                <p className="headline">{c.headline}</p>
                {c.range && <p className="range">{c.range}</p>}
                <ul>
                  {c.facts.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        ))}
      </div>
      <p className="note small">
        Found by a quick engine check ({engineText(data.results.engine)}), so it can miss things; real totals may be
        higher. "Likely between" is a rough range, not a promise. These numbers are frozen and will not change.
        Results id: {data.results_sha256.slice(0, 12)}…
      </p>
    </section>
  )
}

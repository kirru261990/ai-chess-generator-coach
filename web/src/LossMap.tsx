import { useEffect, useState } from 'react'
import { biggestLossZone, leftOutText, searchText, zoneRows, type LossMap as LossMapData } from './lossMapState'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export default function LossMap() {
  const [data, setData] = useState<LossMapData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API}/loss-map`)
      .then(async (res) => {
        const body = await res.json()
        if (!res.ok) throw new Error(body.message ?? `Request failed (${res.status})`)
        setData(body as LossMapData)
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
  if (data.sorted === 0) return <p className="note">No analysed games yet. Sync your games and run the engine pass first.</p>

  const rows = zoneRows(data)
  const biggest = biggestLossZone(data)
  const leftOut = leftOutText(data.left_out)
  return (
    <section className="lossmap">
      <h2>Where you lose</h2>
      <p className="note">
        Each of your {data.sorted} games, sorted by who stood better after Black&apos;s {data.zone_ply / 2}th move (half a pawn
        or more counts as ahead or behind), with how it ended.
        {biggest && (
          <>
            {' '}
            The largest share of your losses starts <strong>{biggest}</strong>.
          </>
        )}
      </p>
      <p className="note legend">Bar: solid is won, grey is drawn, hatched is lost.</p>
      {rows.map((r) => (
        <article key={r.key} className="zone card">
          <div className="card-top">
            <h3>{r.title}</h3>
            {r.lossShare && <span className="chip">{r.lossShare}</span>}
          </div>
          {r.bar && (
            <div className="bar" role="img" aria-label={r.results}>
              <i className="won" style={{ width: `${r.bar.won}%` }} />
              <i className="drawn" style={{ width: `${r.bar.drawn}%` }} />
              <i className="lost" style={{ width: `${r.bar.lost}%` }} />
            </div>
          )}
          <p className="results">{r.results}</p>
          {r.conversion && <p className="results">{r.conversion}</p>}
          {r.caution && <p className="caution"><span className="chip tentative">Too few games</span> {r.caution}</p>}
        </article>
      ))}
      {leftOut && <p className="note">{leftOut}</p>}
      <p className="note">
        This is a quick check ({searchText(data.searches)}), so a position close to the half-pawn line can land in either zone. Practice does
        not change these numbers.
      </p>
    </section>
  )
}

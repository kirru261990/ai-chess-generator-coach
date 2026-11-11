import { useCallback, useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { api } from './api'
import { castleMove, pickMove, pieceColorAt, targetsFrom } from './assessState'
import { answerBanner, historyText, openingCard, sourceLabel, summaryText, type Answer, type OpeningRow, type Question } from './repertoireState'

const DOT = 'radial-gradient(circle, rgba(0,0,0,0.28) 22%, transparent 24%)'

/** Opening repertoire drills (ADR 0022): play a line from move 1. Practice, so always assisted; nothing here counts as evidence. */
export default function Openings() {
  const [rows, setRows] = useState<OpeningRow[]>([])
  const [q, setQ] = useState<Question | null>(null)
  const [ans, setAns] = useState<Answer | null>(null)
  const [done, setDone] = useState<Answer['summary'] | null>(null)
  const [from, setFrom] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api<{ openings: OpeningRow[] }>('/repertoire').then((r) => setRows(r.openings), (e: Error) => setError(e.message))
  }, [])
  useEffect(load, [load])

  async function start(key: string) {
    setBusy(true)
    setError(null)
    try {
      const first = await api<Question>(`/repertoire/${key}/runs`, {})
      setQ(first)
      setAns(null)
      setDone(null)
      setFrom(null)
      setNote(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function submit(move: string) {
    if (!q || busy || ans) return
    setBusy(true)
    setError(null)
    try {
      setAns(await api<Answer>(`/repertoire/${q.key}/runs/${q.run_id}/answer`, { move }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function carryOn() {
    if (!ans) return
    if (ans.next) {
      setQ(ans.next)
      setAns(null)
      setFrom(null)
      setNote(null)
    } else {
      setDone(ans.summary ?? null)
      setQ(null)
      setAns(null)
      load()
    }
  }

  function onSquareClick({ square }: { square: string }) {
    if (!q || ans || busy) return
    const mine = q.side === 'white' ? 'w' : 'b'
    const castle = from ? castleMove(q.legal, q.fen, from, square) : null
    if (castle) return submit(castle)
    if (pieceColorAt(q.fen, square) === mine) {
      setFrom(square === from ? null : square)
      setNote(null)
      return
    }
    if (!from) {
      setNote('Click one of your pieces first, then the square it should go to.')
      return
    }
    const uci = pickMove(q.legal, from, square)
    if (!uci) {
      setNote('That piece cannot go there.')
      return
    }
    setFrom(null)
    submit(uci)
  }

  const styles: Record<string, React.CSSProperties> = {}
  if (q && !ans) {
    if (from) styles[from] = { background: 'rgba(255, 215, 0, 0.45)' }
    for (const t of targetsFrom(q.legal, from)) styles[t] = { background: DOT }
  }
  if (ans) {
    styles[ans.your_uci.slice(2, 4)] = { background: ans.matched ? 'rgba(80, 180, 90, 0.55)' : 'rgba(80, 140, 230, 0.6)' }
    styles[ans.expected_uci.slice(0, 2)] = { background: 'rgba(80, 180, 90, 0.55)' }
    styles[ans.expected_uci.slice(2, 4)] = { background: 'rgba(80, 180, 90, 0.55)' }
  }
  const squareRenderer = ({ square, children }: { square: string; children?: React.ReactNode }) => (
    <div style={{ position: 'relative', width: '100%', height: '100%', ...styles[square] }}>{children}</div>
  )

  const banner = ans ? answerBanner(ans) : null
  return (
    <section className="openings">
      <h2>
        Opening lines <span className="badge">assisted</span>
      </h2>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {q && (
        <>
          <p>
            <strong>{q.name}</strong> · You are {q.side === 'white' ? 'White' : 'Black'}
          </p>
          <p className="history">{historyText(q.history)}</p>
          {!ans && <p>Your move.</p>}
          {sourceLabel(q.source) && <p className="chip">{sourceLabel(q.source)}</p>}
          <div className="board">
            <Chessboard options={{ position: q.fen, boardOrientation: q.side, onSquareClick, squareRenderer, allowDragging: false }} />
          </div>
          {note && (
            <p className="note" aria-live="polite">
              {note}
            </p>
          )}
          {banner && (
            <div className={`banner ${banner.tone}`} role="status">
              <p>{banner.text}</p>
              <button autoFocus onClick={carryOn}>
                {ans?.next ? 'Continue' : 'Finish line'}
              </button>
            </div>
          )}
        </>
      )}
      {!q && (
        <>
          {done && <p className="banner right">Line finished. {summaryText(done)}</p>}
          {rows.map((o) => {
            const c = openingCard(o)
            return (
              <article key={o.key} className="card">
                <div className="card-top">
                  <strong>{c.title}</strong>
                  <span className="chip">{c.side}</span>
                </div>
                {c.progress && <p className="what">{c.progress}</p>}
                {c.engineNote && <p className="what">{c.engineNote}</p>}
                {c.accuracy && <p className="what">{c.accuracy}</p>}
                {c.note && <p className="what caution">{c.note}</p>}
                <button disabled={!c.canStart || busy} onClick={() => start(o.key)}>
                  Practise a line
                </button>
              </article>
            )
          })}
        </>
      )}
    </section>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { api } from './api'
import { castleMove, pickMove, pieceColorAt, targetsFrom } from './assessState'
import { answerBanner, arrowFor, needsResync, recentText, openingCard, sourceLabel, stagesFor, summaryText, type Answer, type Current, type OpeningRow, type Question } from './repertoireState'

const LEARN_KEY = 'openings-show-move'
const DOT = 'radial-gradient(circle, rgba(0,0,0,0.28) 22%, transparent 24%)'

/** Opening repertoire drills (ADR 0022): play a line from move 1. Practice, so always assisted; nothing here counts as evidence. */
function savedLearn(): boolean {
  try {
    return localStorage.getItem(LEARN_KEY) !== 'false'
  } catch {
    return true
  }
}

export default function Openings() {
  const [learn, setLearn] = useState(savedLearn)
  const [wrong, setWrong] = useState<string | null>(null) // the square the player tried: a cross shows there for a moment
  const [shown, setShown] = useState<string | null>(null) // a position drawn between the player's move and the next question
  const timer = useRef<number[]>([])
  const [rows, setRows] = useState<OpeningRow[]>([])
  const [q, setQ] = useState<Question | null>(null)
  const [ans, setAns] = useState<Answer | null>(null)
  const [ended, setEnded] = useState<{ key: string; name: string; side: 'white' | 'black'; fen: string; summary: Answer['summary'] | null } | null>(null)
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
      const first = await api<Question>(`/repertoire/${key}/runs?learn=${learn}`, {})
      setQ(first)
      setAns(null)
      setEnded(null)
      setFrom(null)
      setNote(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function submit(move: string) {
    if (!q || busy || (ans && !ans.retry)) return
    setBusy(true)
    setError(null)
    try {
      const a = await api<Answer>(`/repertoire/${q.key}/runs/${q.run_id}/answer`, { move, ply: q.ply })
      if (a.retry) {
        // Not the line's move: the board does not change (the piece stays where it was), a cross shows on the square, and the
        // player tries again at once.
        setWrong(move.slice(2, 4))
        clearTimers()
        timer.current.push(window.setTimeout(() => setWrong(null), 1500))
        setAns(a)
      } else {
        setWrong(null)
        setAns(a)
        clearTimers()
        // The player's move is drawn at once; the opponent's reply follows a beat later, as in Practice.
        for (const st of stagesFor(a)) {
          timer.current.push(
            window.setTimeout(() => {
              setShown(st.fen)
              if (st.then) finish(a)
            }, st.afterMs),
          )
        }
      }
    } catch (e) {
      const err = e as Error & { code?: string; status?: number }
      if (needsResync(err)) await resync(q)
      else setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  /** The answer may or may not have been taken (the response was lost, or the question was already answered): ask where the run is. */
  async function resync(from: Question) {
    clearTimers()
    setWrong(null)
    setShown(null)
    try {
      const now = await api<Current>(`/repertoire/${from.key}/runs/${from.run_id}`)
      setAns(null)
      setFrom(null)
      if (now.finished) {
        setEnded({ key: from.key, name: from.name, side: from.side, fen: now.fen, summary: now.summary })
        setQ(null)
        load()
      } else {
        setQ(now.question)
        setNote('Caught up with where the line is.')
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }

  function clearTimers() {
    for (const t of timer.current) window.clearTimeout(t)
    timer.current = []
  }

  function finish(a: Answer) {
    if (a.next) {
      setShown(null)
      setQ(a.next)
      setAns(null)
      setFrom(null)
      setNote(null)
    } else {
      // The line is over: keep its last position on the board with the summary and the next steps, instead of dropping back to the list.
      setEnded(q ? { key: q.key, name: q.name, side: q.side, fen: a.reply_fen ?? shown ?? q.fen, summary: a.summary ?? null } : null)
      setShown(null)
      setQ(null)
      setAns(null)
      load()
    }
  }

  useEffect(() => clearTimers, [])

  function pickLearn(on: boolean) {
    setLearn(on)
    try {
      localStorage.setItem(LEARN_KEY, String(on))
    } catch {
      /* the choice is simply not remembered */
    }
  }

  function onSquareClick({ square }: { square: string }) {
    if (!q || (ans && !ans.retry) || busy) return
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
  if (q && !(ans && ans.matched)) {
    if (from) styles[from] = { background: 'rgba(255, 215, 0, 0.45)' }
    for (const t of targetsFrom(q.legal, from)) styles[t] = { background: DOT }
  }
  if (ans?.matched) {
    styles[ans.your_uci.slice(2, 4)] = { background: 'rgba(80, 180, 90, 0.55)' }
  }
  const squareRenderer = ({ square, children }: { square: string; children?: React.ReactNode }) => (
    <div style={{ position: 'relative', width: '100%', height: '100%', ...styles[square] }}>
      {children}
      {wrong === square && (
        <span className="move-badge blunder" title="Not the line's move" aria-label="Not the line's move">
          ✕
        </span>
      )}
      {ans?.matched && square === ans.your_uci.slice(2, 4) && (
        <span className="move-badge best" title="Right" aria-label="Right">
          ✓
        </span>
      )}
    </div>
  )

  const banner = ans && !ans.matched ? answerBanner(ans) : null // only a wrong try gets a message; a right move shows just the tick
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
          <p className="run-head">
            <strong>{q.name}</strong> · You are {q.side === 'white' ? 'White' : 'Black'}
            {sourceLabel(q.source) && <span className="chip engine-chip">Engine line</span>}
          </p>
          <p className="history">{recentText(q.history)}</p>
          <div className="board">
            <Chessboard options={{ position: shown ?? q.fen, boardOrientation: q.side, onSquareClick, squareRenderer, allowDragging: false, arrows: arrowFor(q, ans) }} />
          </div>
          {/* One row of fixed height under the board for a message, so the board never moves when a message comes and goes. */}
          <div className="status-row" aria-live="polite">
            {banner ? <span className={`banner ${banner.tone}`}>{banner.text}</span> : note}
          </div>
        </>
      )}
      {!q && ended && (
        <div className="ended">
          <p>
            <strong>{ended.name}</strong> · line finished
          </p>
          <p className="banner right" role="status">
            {ended.summary ? summaryText(ended.summary) : 'Line finished.'}
          </p>
          <div className="board">
            <Chessboard options={{ position: ended.fen, boardOrientation: ended.side, allowDragging: false }} />
          </div>
          <p>
            <button autoFocus disabled={busy} onClick={() => start(ended.key)}>
              Another line
            </button>{' '}
            <button onClick={() => setEnded(null)}>Back to openings</button>
          </p>
        </div>
      )}
      {!q && !ended && (
        <>
          <label className="threat-toggle" title="Draw the move to play as an arrow while you learn a line">
            <input type="checkbox" checked={learn} onChange={(e) => pickLearn(e.target.checked)} /> Show the move as an arrow
          </label>
          <p className="note">With the arrow on you learn a line. Switch it off to recall it: a wrong move shows a cross and you try again.</p>
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

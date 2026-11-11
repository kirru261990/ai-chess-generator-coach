import { useCallback, useEffect, useRef, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { api } from './api'
import { castleMove, pickMove, pieceColorAt, targetsFrom } from './assessState'
import { answerBanner, arrowFor, historyText, openingCard, sourceLabel, stagesFor, summaryText, type Answer, type OpeningRow, type Question } from './repertoireState'

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
      const first = await api<Question>(`/repertoire/${key}/runs?learn=${learn}`, {})
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
    if (!q || busy || (ans && !ans.retry)) return
    setBusy(true)
    setError(null)
    try {
      const a = await api<Answer>(`/repertoire/${q.key}/runs/${q.run_id}/answer`, { move })
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
      setError((e as Error).message)
    } finally {
      setBusy(false)
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
      setShown(null)
      setDone(a.summary ?? null)
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
            <Chessboard options={{ position: shown ?? q.fen, boardOrientation: q.side, onSquareClick, squareRenderer, allowDragging: false, arrows: arrowFor(q, ans) }} />
          </div>
          {note && (
            <p className="note" aria-live="polite">
              {note}
            </p>
          )}
          {banner && (
            <div className={`banner ${banner.tone}`} role="status">
              <p>{banner.text}</p>

            </div>
          )}
        </>
      )}
      {!q && (
        <>
          <label className="threat-toggle" title="Draw the move to play as an arrow while you learn a line">
            <input type="checkbox" checked={learn} onChange={(e) => pickLearn(e.target.checked)} /> Show the move as an arrow
          </label>
          <p className="note">With the arrow on you learn a line. Switch it off to recall it: a wrong move shows a cross and you try again.</p>
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

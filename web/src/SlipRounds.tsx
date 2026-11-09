import { useCallback, useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { api } from './api'
import { castleMove, pickMove, pieceColorAt, targetsFrom } from './assessState'
import {
  answerLine, boardMarks, clampStep, reviewFrame, roundLine, timerState, TIMER_CHOICES,
  type Answer, type Current, type Line, type Question, type RoundSummary,
} from './slipRoundState'

const DOT = 'radial-gradient(circle, rgba(0,0,0,0.28) 22%, transparent 24%)'
const GREEN = 'rgba(80, 180, 90, 0.55)'
const TIMER_KEY = 'slip-rounds-timer'

type RoundRow = { round: number; finished: boolean; summary: RoundSummary }

function savedTimer(): number {
  try {
    const v = Number(localStorage.getItem(TIMER_KEY))
    return TIMER_CHOICES.some((c) => c.seconds === v) && localStorage.getItem(TIMER_KEY) !== null ? v : 15
  } catch {
    return 15
  }
}

/** Slip rounds (ADR 0020, 0021): ten positions at your real game pace. Practice, so always assisted; nothing here counts as evidence. */
export default function SlipRounds() {
  const [timer, setTimer] = useState(savedTimer)
  const [q, setQ] = useState<Question | null>(null)
  const [ans, setAns] = useState<Answer | null>(null)
  const [done, setDone] = useState<{ round: number; summary: RoundSummary } | null>(null)
  const [rounds, setRounds] = useState<RoundRow[]>([])
  const [from, setFrom] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(0)
  const [line, setLine] = useState<Line>('mine')
  const [step, setStep] = useState(0)
  const [shownAt, setShownAt] = useState(0)

  const loadRounds = useCallback(() => {
    api<RoundRow[]>('/drills/rounds').then(setRounds, (e: Error) => setError(e.message))
  }, [])
  useEffect(loadRounds, [loadRounds])

  // The countdown only ticks while a question is open; the server's clock decides what counts as over time.
  useEffect(() => {
    if (!q || ans) return
    const id = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(id)
  }, [q, ans])

  function pickTimer(seconds: number) {
    setTimer(seconds)
    try {
      localStorage.setItem(TIMER_KEY, String(seconds))
    } catch {
      /* the choice is simply not remembered */
    }
  }

  async function next() {
    setBusy(true)
    setError(null)
    try {
      const c = await api<Current>(`/drills/rounds/current?timer=${timer}`)
      setAns(null)
      setFrom(null)
      setNote(null)
      setLine('mine')
      setStep(0)
      if (c.done) {
        setQ(null)
        setDone({ round: c.round, summary: c.summary })
        loadRounds()
      } else {
        setDone(null)
        setQ(c)
        const t = Date.now()
        setShownAt(t)
        setNow(t)
      }
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
      const a = await api<Answer>('/drills/rounds/current/answer', { drill_id: q.drill_id, move })
      setAns(a)
      setLine('mine')
      setStep(0)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function onSquareClick({ square }: { square: string }) {
    if (!q || ans || busy) return
    const mine = q.side === 'white' ? 'w' : 'b'
    const castle = from ? castleMove(q.legal_moves, q.fen, from, square) : null
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
    const uci = pickMove(q.legal_moves, from, square)
    if (!uci) {
      setNote('That piece cannot go there.')
      return
    }
    setFrom(null)
    submit(uci)
  }

  const review = ans?.review ?? null
  const frame = review ? reviewFrame(review, line, step) : null
  const marks = frame && ans ? boardMarks(frame, line, { uci: ans.your_uci, matched: ans.matched }) : null
  const clock = q && !ans ? timerState(q.timer_s, now - shownAt) : null

  const styles: Record<string, React.CSSProperties> = {}
  if (q && !ans) {
    if (from) styles[from] = { background: 'rgba(255, 215, 0, 0.45)' }
    for (const t of targetsFrom(q.legal_moves, from)) styles[t] = { background: DOT }
  }
  if (ans && !review) {
    for (const u of ans.checked_uci) {
      styles[u.slice(0, 2)] = { background: GREEN }
      styles[u.slice(2, 4)] = { background: GREEN }
    }
  }

  // The board library skips its own square styling when a custom renderer returns something, so this applies `styles` itself.
  const squareRenderer = ({ square, children }: { square: string; children?: React.ReactNode }) => (
    <div style={{ position: 'relative', width: '100%', height: '100%', ...styles[square] }}>
      {children}
      {marks?.badge && square === marks.badge.square && (
        <span className={`move-badge ${marks.badge.tone}`} title={marks.badge.label} aria-label={marks.badge.label}>{marks.badge.symbol}</span>
      )}
    </div>
  )

  const open = rounds.find((r) => !r.finished)
  return (
    <div className="slip-rounds">
      <h2>Slip rounds <span className="badge">assisted</span></h2>
      {error && <p className="error">{error}</p>}

      {q ? (
        <>
          <p>
            <strong>Round {q.round}</strong> · position {q.position} of {q.total} · You are {q.side === 'white' ? 'White' : 'Black'}
          </p>
          {!ans && <p>{q.question}</p>}
          {clock && (
            <div className={`slip-clock ${clock.level}`} role="timer" aria-label={`Time: ${clock.label}`}>
              <div className="slip-clock-bar"><div style={{ width: `${Math.round(clock.fraction * 100)}%` }} /></div>
              <span>{clock.label}</span>
            </div>
          )}
          <div className="board">
            <Chessboard
              options={{
                position: frame ? frame.fen : q.fen,
                boardOrientation: q.side,
                allowDragging: false,
                onSquareClick,
                squareStyles: styles,
                arrows: marks ? marks.arrows : [],
                squareRenderer,
                id: 'slip-board',
              }}
            />
          </div>
          {note && <p className="muted">{note}</p>}
          {ans && (
            <div className="feedback">
              <p title={ans.matched ? undefined : 'Not one of the engine-checked moves. That does not mean it is bad: the engine did not rule on it.'}><strong>{answerLine(ans)}</strong></p>
              {review && frame ? (
                <div className="slip-review">
                  <div className="slip-tabs">
                    {(['mine', 'better'] as Line[]).map((l) => (
                      <button key={l} className={`${l} ${line === l ? 'on' : ''}`} onClick={() => { setLine(l); setStep(0) }}>
                        {l === 'mine' ? 'Your move' : 'Better move'}
                      </button>
                    ))}
                  </div>
                  <div className="slip-caption">
                    <strong>{frame.caption}</strong>
                    {frame.points && <span>{frame.points}</span>}
                  </div>
                  <div className="slip-steps">
                    <button onClick={() => setStep(clampStep(review, line, step - 1))} disabled={step === 0}>Back</button>
                    <span>{step} of {frame.last}</span>
                    <button className="primary" onClick={() => setStep(clampStep(review, line, step + 1))} disabled={step >= frame.last}>Next move</button>
                  </div>
                </div>
              ) : (
                <p className="muted">No line is stored for this position.</p>
              )}
              <div className="slip-cause">
                <p><strong>{ans.cause.sentence}</strong></p>
                {ans.cause.habit && <p className="slip-habit">{ans.cause.habit}</p>}
              </div>
              <button onClick={next} disabled={busy}>Next position</button>
            </div>
          )}
        </>
      ) : done ? (
        <>
          <p><strong>Round {done.round} finished.</strong></p>
          <p>{roundLine(done.summary)}</p>
          <button onClick={next} disabled={busy}>Start next round</button>
        </>
      ) : (
        <>
          <fieldset className="slip-timer-choice">
            <legend>Time for each position</legend>
            {TIMER_CHOICES.map((c) => (
              <label key={c.seconds}>
                <input type="radio" name="slip-timer" checked={timer === c.seconds} onChange={() => pickTimer(c.seconds)} />
                <strong>{c.label}</strong> <span className="muted">({c.hint})</span>
              </label>
            ))}
          </fieldset>
          <button onClick={next} disabled={busy}>
            {open && open.summary.answered > 0 ? `Continue round ${open.round}` : `Start round ${rounds.length + (open ? 0 : 1)}`}
          </button>
          {rounds.length > 0 && (
            <ul className="slip-rounds-list">
              {rounds.map((r) => (
                <li key={r.round}>
                  Round {r.round}{r.finished ? '' : ' (in progress)'}: {roundLine(r.summary)}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

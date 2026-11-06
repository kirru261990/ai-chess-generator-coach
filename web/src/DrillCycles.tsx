import { useCallback, useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { api } from './api'
import { castleMove, pickMove, pieceColorAt, targetsFrom } from './assessState'
import {
  compareLine, formatDuration, matchLine, nextGoal,
  type Current, type CycleRow, type Feedback, type Overview, type Question,
} from './drillCycleState'

const DOT = 'radial-gradient(circle, rgba(0,0,0,0.28) 22%, transparent 24%)'
const GREEN = 'rgba(80, 180, 90, 0.55)'

/** Drill cycles (ADR 0018): the same fixed set of drills again and again, each pass faster. Practice, so always assisted. */
export default function DrillCycles() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [q, setQ] = useState<Question | null>(null)
  const [fb, setFb] = useState<Feedback | null>(null)
  const [from, setFrom] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const loadOverview = useCallback(() => {
    api<Overview>('/drills/cycles').then(setOverview, (e: Error) => setError(e.message))
  }, [])
  useEffect(loadOverview, [loadOverview])

  async function next() {
    setBusy(true)
    setError(null)
    try {
      const c = await api<Current>('/drills/cycles/current')
      setFb(null)
      setFrom(null)
      setNote(null)
      if (c.done) {
        setQ(null)
        setOverview(c.summary)
      } else {
        setQ(c)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function submit(move: string) {
    if (!q || busy) return
    setBusy(true)
    setError(null)
    try {
      setFb(await api<Feedback>('/drills/cycles/current/answer', { drill_id: q.drill_id, move }))
      loadOverview()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function onSquareClick({ square }: { square: string }) {
    if (!q || fb || busy) return
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

  const styles: Record<string, React.CSSProperties> = {}
  if (q && !fb) {
    if (from) styles[from] = { background: 'rgba(255, 215, 0, 0.45)' }
    for (const t of targetsFrom(q.legal_moves, from)) styles[t] = { background: DOT }
  }
  if (fb) {
    for (const u of fb.checked_uci) {
      styles[u.slice(0, 2)] = { background: GREEN }
      styles[u.slice(2, 4)] = { background: GREEN }
    }
  }

  const rows = overview?.cycles ?? []
  const open = rows.find((r) => !r.finished)
  const goal = nextGoal(rows)

  return (
    <div className="drill-cycles">
      <h2>Drill cycles</h2>
      <p className="muted">
        The same {overview?.size ?? 50} drills, again and again, each pass faster. This is Practice: the answer is shown after every move.
        Speed only counts if you keep matching, so slow down if you start guessing.
      </p>
      {error && <p className="error">{error}</p>}

      {q ? (
        <>
          <p>
            <strong>Cycle {q.cycle}</strong> · drill {q.position} of {q.total} · You are {q.side === 'white' ? 'White' : 'Black'}
          </p>
          <p>{q.question}</p>
          <div className="board">
            <Chessboard options={{ position: q.fen, boardOrientation: q.side, allowDragging: false, onSquareClick, squareStyles: styles, id: 'drill-board' }} />
          </div>
          {note && <p className="muted">{note}</p>}
          {fb && (
            <div className="feedback">
              <p>
                <strong>{fb.matched ? `Yes, ${fb.your_move} is one of the checked moves.` : `${fb.your_move} is not one of the checked moves.`}</strong>{' '}
                Checked: {fb.checked_moves.join(', ')}. Time: {formatDuration(fb.elapsed_ms)}.
              </p>
              <p>{fb.note}</p>
              {fb.not_checked && <p className="muted">{fb.not_checked}</p>}
              <button onClick={next} disabled={busy}>Next drill</button>
            </div>
          )}
        </>
      ) : (
        <>
          <button onClick={next} disabled={busy}>
            {open && open.answered > 0 ? `Continue cycle ${open.number}` : `Start cycle ${rows.length + (open ? 0 : 1)}`}
          </button>
          {goal && <p>{goal}</p>}
          {rows.length > 0 && (
            <table className="cycle-table">
              <thead><tr><th>Cycle</th><th>Matched</th><th>Time</th><th>Per drill</th><th /></tr></thead>
              <tbody>{rows.map((r) => <CycleLine key={r.number} r={r} />)}</tbody>
            </table>
          )}
          <p className="muted">
            Matched means you played a move the engine checked. Another move is not called wrong: the engine did not rule on it.
            With 50 drills, a few matches either way is noise, not progress.
          </p>
        </>
      )}
    </div>
  )
}

function CycleLine({ r }: { r: CycleRow }) {
  const cmp = compareLine(r)
  return (
    <tr>
      <td>{r.number}{r.finished ? '' : ' (in progress)'}</td>
      <td>{matchLine(r)}</td>
      <td>{formatDuration(r.total_ms)}</td>
      <td>{r.median_ms === null ? '' : `${formatDuration(r.median_ms)} (middle)`}</td>
      <td>{cmp}</td>
    </tr>
  )
}

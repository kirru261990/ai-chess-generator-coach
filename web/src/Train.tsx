import { useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import './App.css'
import Rapid from './Rapid'
import {
  KIND_LABEL,
  summarise,
  summaryLines,
  uciForClick,
  type Answer,
  type AttemptResult,
  type ItemOutcome,
  type Motif,
  type RapidView,
  type Session,
} from './trainState'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const HINT_STEPS = ['Think', 'Idea', 'Piece', 'Why', 'Move']

type HintStep = { level: number; kind: string; text: string; from?: string; to?: string; uci?: string }
type Progress = {
  sessions: number
  retest_due: number
  rapid?: { sessions: number; attempts: number }
  by_motif: Record<
    Motif,
    {
      practice_first_tries: number
      practice_first_try_correct: number
      practice_first_try_correct_unassisted: number
      held_out_attempts: number
      held_out_correct: number
    }
  >
}

const MOTIFS: { key: Motif; title: string; blurb: string }[] = [
  { key: 'hanging_own', title: 'Stop leaving pieces hanging', blurb: 'Positions from your own games where a piece of yours could be taken.' },
  { key: 'missed_free', title: 'Take free pieces', blurb: 'Your own missed captures, plus puzzles where a piece is simply free.' },
]

async function call<T>(path: string, init?: RequestInit): Promise<{ ok: true; data: T } | { ok: false; message: string }> {
  try {
    const res = await fetch(`${API}${path}`, init)
    const data = await res.json().catch(() => null)
    if (!res.ok) return { ok: false, message: (data as { message?: string } | null)?.message ?? `error ${res.status}` }
    return { ok: true, data: data as T }
  } catch {
    return { ok: false, message: 'Could not reach the server. Check that it is running.' }
  }
}

export default function Train() {
  const [progress, setProgress] = useState<Progress | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [selectedPiece, setSelectedPiece] = useState<string | null>(null)
  const [ended, setEnded] = useState(false)
  const [hint, setHint] = useState<HintStep[]>([])
  const [result, setResult] = useState<AttemptResult | null>(null)
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [outcomes, setOutcomes] = useState<ItemOutcome[]>([])
  const [hintedItems, setHintedItems] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rapid, setRapid] = useState<RapidView | null>(null)

  useEffect(() => {
    if (session) return
    void call<Progress>('/training/progress').then((r) => setProgress(r.ok ? r.data : null))
  }, [session])

  async function startRapid() {
    setBusy(true)
    setError(null)
    const r = await call<RapidView>('/training/rapid', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit_s: 10 }),
    })
    setBusy(false)
    if (!r.ok) return setError(r.message)
    setRapid(r.data)
  }

  async function start(motif: Motif) {
    setBusy(true)
    setError(null)
    const r = await call<Session>('/training/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ motif }),
    })
    setBusy(false)
    if (!r.ok) return setError(r.message)
    setSession(r.data)
    setEnded(false)
    resetItem(0)
    setOutcomes([])
    setHintedItems(new Set())
  }

  function resetItem(i: number) {
    setIndex(i)
    setSelected(null)
    setSelectedPiece(null)
    setHint([])
    setResult(null)
    setAnswer(null)
    setError(null)
  }

  const item = session?.items[index]
  const finishedItem = answer !== null
  const allDone = ended

  async function askHint(level: number) {
    if (!session || !item) return
    setBusy(true)
    const r = await call<{ steps: HintStep[] }>(`/training/sessions/${session.id}/items/${item.index}/hint?level=${level}`)
    setBusy(false)
    if (!r.ok) return setError(r.message)
    setError(null)
    setHint(r.data.steps)
    setHintedItems((s) => new Set(s).add(item.index))
  }

  function record(res: AttemptResult | null, ans: Answer, gave: boolean) {
    if (!item) return
    setAnswer(ans)
    setOutcomes((o) => [
      ...o,
      {
        index: item.index,
        kind: item.kind,
        correct: res?.correct ?? false,
        firstTry: res ? res.first_try : true,
        assisted: res ? res.assisted : true,
        gaveUp: gave,
      },
    ])
  }

  async function giveUp() {
    if (!session || !item) return
    setBusy(true)
    const r = await call<{ answer: Answer }>(`/training/sessions/${session.id}/items/${item.index}/give-up`, { method: 'POST' })
    setBusy(false)
    if (!r.ok) return setError(r.message)
    record(null, r.data.answer, true)
  }

  async function onSquareClick({ piece, square }: { piece: { pieceType: string } | null; square: string }) {
    if (!session || !item || busy || finishedItem) return
    const mine = piece !== null && piece.pieceType[0] === (item.side === 'white' ? 'w' : 'b')
    if (mine) {
      setSelectedPiece(square === selected ? null : piece.pieceType)
      return setSelected(square === selected ? null : square)
    }
    if (!selected) return
    const from = selected
    setSelected(null)
    setSelectedPiece(null)
    setBusy(true)
    const r = await call<AttemptResult>(`/training/sessions/${session.id}/items/${item.index}/attempt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uci: uciForClick(from, square, selectedPiece) }),
    })
    setBusy(false)
    if (!r.ok) return setError(r.message)
    setError(null)
    setResult(r.data)
    if (r.data.finished && r.data.answer) record(r.data, r.data.answer, false)
  }

  // ---------------------------------------------------------------- screens
  if (rapid) return <Rapid view={rapid} onExit={() => setRapid(null)} />
  if (!session) {
    return (
      <main className="train">
        <h2>Train</h2>
        <p>
          Five positions: mostly your own mistakes. Try each one yourself first; the hints come in steps, and any hint is marked
          &ldquo;assisted&rdquo;. The last position is a test with no hints and one try.
        </p>
        {MOTIFS.map((m) => {
          const p = progress?.by_motif?.[m.key]
          return (
            <section key={m.key} className="hint-card">
              <h3>{m.title}</h3>
              <p>{m.blurb}</p>
              {p && p.practice_first_tries > 0 && (
                <p className="hint-count">
                  So far: {p.practice_first_try_correct} of {p.practice_first_tries} right on the first try
                  {p.held_out_attempts > 0 && `; test positions ${p.held_out_correct} of ${p.held_out_attempts}`}
                </p>
              )}
              <button className="primary" disabled={busy} onClick={() => void start(m.key)}>
                Start a session
              </button>
            </section>
          )
        })}
        <section className="hint-card">
          <h3>Rapid drill</h3>
          <p>
            Twelve positions from your own games, 10 seconds each, one try, no labels. Some need a move, some need nothing, like a
            real game. You see their last move arrive first.
          </p>
          {progress?.rapid && progress.rapid.attempts > 0 && (
            <p className="hint-count">{progress.rapid.sessions} drill(s) so far, {progress.rapid.attempts} positions played</p>
          )}
          <button className="primary" disabled={busy} onClick={() => void startRapid()}>
            Start a rapid drill
          </button>
        </section>
        {progress && progress.retest_due > 0 && <p>{progress.retest_due} position(s) you missed a week or more ago are due for a retest.</p>}
        {error && <p role="alert">{error}</p>}
      </main>
    )
  }

  if (allDone) {
    return (
      <main className="train">
        <h2>Session done</h2>
        <ul>{summaryLines(summarise(outcomes)).map((l) => <li key={l}>{l}</li>)}</ul>
        <p>Your real test is your next games: the same blind-spot rate per 100 moves, compared with your frozen baseline.</p>
        <button className="primary" onClick={() => setSession(null)}>Back to Train</button>
      </main>
    )
  }

  if (!item) return null
  const shown = hint
  const fromSquare = shown.find((s) => s.from)?.from
  const moveStep = shown.find((s) => s.kind === 'move')
  const squareStyles: Record<string, React.CSSProperties> = {}
  if (selected) squareStyles[selected] = { background: 'rgba(255, 200, 0, 0.45)' }
  if (fromSquare && !finishedItem) squareStyles[fromSquare] = { background: 'rgba(60, 170, 90, 0.35)' }
  const arrows = moveStep?.from && moveStep.to && !finishedItem ? [{ startSquare: moveStep.from, endSquare: moveStep.to, color: 'rgba(60, 170, 90, 0.8)' }] : []
  if (answer && finishedItem) {
    squareStyles[answer.uci.slice(0, 2)] = { background: 'rgba(60, 170, 90, 0.35)' }
    squareStyles[answer.uci.slice(2, 4)] = { background: 'rgba(60, 170, 90, 0.55)' }
  }
  const level = shown.length
  const heldOut = item.kind === 'held_out'

  return (
    <main className="train layout">
      <div className="board-col">
        <div className="board">
          <Chessboard
            options={{
              position: item.fen,
              boardOrientation: item.side,
              allowDragging: false,
              onSquareClick,
              squareStyles,
              arrows,
              id: 'train-board',
            }}
          />
        </div>
      </div>
      <aside className="side-col">
        <p className="status-line">
          <strong>
            Position {index + 1} of {session.items.length}
          </strong>{' '}
          · {KIND_LABEL[item.kind]}
          {hintedItems.has(item.index) && <span className="badge"> assisted</span>}
        </p>
        <p>
          {session.motif_label[0].toUpperCase() + session.motif_label.slice(1)}. You play {item.side}. Click a piece, then where it goes.
        </p>

        {result && !result.correct && !finishedItem && (
          <section className="hint-card" role="status">
            <h3>Not quite</h3>
            <ul>{result.facts.map((f) => <li key={f}>{f}</li>)}</ul>
          </section>
        )}

        {!finishedItem && !heldOut && (
          <section className="hint-card" aria-live="polite">
            <h3>Need help? <span className="hint-count">{level > 0 ? `step ${level} of ${HINT_STEPS.length}` : 'try it yourself first'}</span></h3>
            {shown.length > 0 && (
              <ul className="hint-steps">
                {shown.map((st) => <li key={st.level}><b>{HINT_STEPS[st.level - 1]}:</b> {st.text}</li>)}
              </ul>
            )}
            <div className="hint-actions">
              {level < HINT_STEPS.length && (
                <button className="primary" disabled={busy} onClick={() => void askHint(level + 1)}>
                  {level === 0 ? '💡 Give me a hint' : `Show step ${level + 1}: ${HINT_STEPS[level]}`}
                </button>
              )}
              <button disabled={busy} onClick={() => void giveUp()}>Show me the answer</button>
            </div>
          </section>
        )}

        {finishedItem && answer && (
          <section className="hint-card" role="status">
            <h3>{result?.correct ? 'Right' : heldOut ? 'Not this time' : 'The move was'}: {answer.san}</h3>
            {result?.correct && result.accepted_by === 'engine_equivalent' && <p>The engine rates your move about as good as the one we had in mind.</p>}
            <p>{answer.why}</p>
            {answer.played_san && <p>In your game you played {answer.played_san}.</p>}
            <button
              className="primary"
              onClick={() => (index + 1 < session.items.length ? resetItem(index + 1) : setEnded(true))}
            >
              {index + 1 < session.items.length ? 'Next position' : 'See summary'}
            </button>
          </section>
        )}
        {error && <p role="alert">{error}</p>}
      </aside>
    </main>
  )
}

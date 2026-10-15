import { useCallback, useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import {
  NO_THREAT,
  castleMove,
  pickMove,
  pieceColorAt,
  poolShortfall,
  scoreLine,
  scoreNotes,
  tapRefusal,
  startLabel,
  tapWords,
  targetsFrom,
  type AssessmentView,
  type HomeType,
  type ResultItem,
  type Results,
} from './assessState'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const RESULTS_POLL_MS = 4000 // while the random-guess move rate is still being calculated

type Screen = { name: 'home' } | { name: 'test'; id: number } | { name: 'results'; id: number }

async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message ?? data.error ?? `request failed (${res.status})`)
  return data as T
}

/** PRD v2 home and the unassisted baseline test (Step 2). No hints, no eval, no feedback until the end. */
export default function Mistakes() {
  const [screen, setScreen] = useState<Screen>({ name: 'home' })
  if (screen.name === 'test') return <Test id={screen.id} onDone={() => setScreen({ name: 'results', id: screen.id })} />
  if (screen.name === 'results') return <ResultsPage id={screen.id} onBack={() => setScreen({ name: 'home' })} />
  return <Home onOpen={(t) => {
    if (t.baseline?.status === 'submitted') setScreen({ name: 'results', id: t.baseline.assessment_id })
    else if (t.baseline) setScreen({ name: 'test', id: t.baseline.assessment_id })
  }} onStarted={(id) => setScreen({ name: 'test', id })} />
}

function Home({ onOpen, onStarted }: { onOpen: (t: HomeType) => void; onStarted: (id: number) => void }) {
  const [types, setTypes] = useState<HomeType[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<{ types: HomeType[] }>('/coach/home').then((h) => setTypes(h.types)).catch((e: Error) => setError(e.message))
  }, [])

  function go(t: HomeType) {
    if (t.baseline) return onOpen(t)
    setBusy(true)
    api<{ assessment_id: number }>('/coach/assessments/baseline', { mistake_type: t.mistake_type })
      .then((s) => onStarted(s.assessment_id))
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false))
  }

  return (
    <div className="spots">
      <h2>Test yourself first</h2>
      <p className="note">
        Before practising a kind of mistake, take a short test of 5 positions from your own games that you have not seen
        here before. There is no help and no feedback until you finish. This is your starting point, so later tests can show
        whether practice helped.
      </p>
      {error && <p className="error">{error}</p>}
      {!types && !error && <p>Loading…</p>}
      <div className="columns">
        {types?.map((t) => {
          const label = startLabel(t)
          const short = poolShortfall(t.pool)
          return (
            <div className="card" key={t.mistake_type}>
              <h3>{t.label}</h3>
              <p className="what">
                Positions kept aside for tests: {t.pool.mistake_positions} with this mistake (need{' '}
                {t.pool.needed_mistake_positions}) and {t.pool.clean_positions} with nothing wrong (need{' '}
                {t.pool.needed_clean_positions}).
              </p>
              {short && <p className="note">{short}</p>}
              {t.baseline?.status === 'submitted' && <p className="note">Starting test done.</p>}
              {label && <button disabled={busy} onClick={() => go(t)}>{label}</button>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Test({ id, onDone }: { id: number; onDone: () => void }) {
  const [view, setView] = useState<AssessmentView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tap, setTap] = useState<string | null>(null) // a square, or NO_THREAT
  const [step, setStep] = useState<'tap' | 'move'>('tap')
  const [from, setFrom] = useState<string | null>(null)
  const [move, setMove] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null) // why a click did nothing (rules only, never a hint)

  const load = useCallback((v: AssessmentView) => {
    setView(v)
    setTap(null)
    setStep('tap')
    setFrom(null)
    setMove(null)
    setNote(null)
  }, [])

  useEffect(() => {
    api<AssessmentView>(`/coach/assessments/${id}`).then(load).catch((e: Error) => setError(e.message))
  }, [id, load])

  if (error) return <div className="app"><p className="error">{error}</p></div>
  if (!view) return <div className="app"><p>Loading…</p></div>

  const cur = view.current
  if (!cur) {
    return (
      <div className="app">
        <h2>{view.label}</h2>
        <p>You answered all {view.total} positions. Submit to see your answers and your score.</p>
        <button disabled={busy} onClick={() => {
          setBusy(true)
          api(`/coach/assessments/${id}/submit`, {}).then(onDone).catch((e: Error) => setError(e.message))
            .finally(() => setBusy(false))
        }}>Submit and see results</button>
      </div>
    )
  }

  const mine = cur.side_to_move === 'white' ? 'w' : 'b'
  function onSquareClick({ square }: { square: string }) {
    if (!cur || busy) return
    const color = pieceColorAt(cur.fen, square)
    if (step === 'tap') {
      if (!color) return
      const why = tapRefusal(tap, square, cur.tap_squares, view!.mistake_type)
      setNote(why)
      if (!why) setTap(square === tap ? null : square)
      return
    }
    const castle = from ? castleMove(cur.legal_moves, cur.fen, from, square) : null
    if (castle) {
      setFrom(null)
      setMove(castle)
      setNote(null)
      return
    }
    if (color === mine) {
      setFrom(square === from ? null : square)
      setMove(null)
      setNote(null)
      return
    }
    if (!from) {
      setNote('Click one of your pieces first, then the square it should go to.')
      return
    }
    const uci = pickMove(cur.legal_moves, from, square)
    setFrom(null)
    setMove(uci)
    setNote(uci ? null : 'That move is not possible here. Click one of your pieces, then a marked square.')
  }

  function send() {
    if (!cur || !tap || !move) return
    setBusy(true)
    api<AssessmentView>(`/coach/assessments/${id}/items`, { ord: cur.ord, recognition: tap, move })
      .then(load)
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false))
  }

  const styles: Record<string, React.CSSProperties> = {}
  if (tap && tap !== NO_THREAT) styles[tap] = { background: 'rgba(255, 200, 0, 0.6)' }
  if (from) styles[from] = { background: 'rgba(80, 140, 230, 0.45)' }
  for (const sq of targetsFrom(cur.legal_moves, from)) {
    // a dot on an empty square, a ring around a piece that can be taken
    const mark = pieceColorAt(cur.fen, sq)
      ? 'radial-gradient(circle, transparent 58%, rgba(0,0,0,0.25) 60%)'
      : 'radial-gradient(circle, rgba(0,0,0,0.25) 22%, transparent 24%)'
    styles[sq] = { ...styles[sq], backgroundImage: mark }
  }
  const arrows = move ? [{ startSquare: move.slice(0, 2), endSquare: move.slice(2, 4), color: 'rgba(80, 140, 230, 0.85)' }] : []
  const askWhat = view.mistake_type === 'M1'
    ? 'Which of YOUR pieces can the other side win? Tap it, or choose "No immediate threat".'
    : 'Which of THEIR pieces can you win for free? Tap it, or choose "No immediate threat".'

  return (
    <div className="app">
      <h2>{view.label}: position {cur.number} of {view.total}</h2>
      {cur.number === 1 && <p className="note">{view.cue}</p>}
      <p className="status-line">You play {cur.side_to_move}, and it is your move.</p>
      <div className="board">
        <Chessboard options={{
          position: cur.fen,
          boardOrientation: cur.side_to_move,
          allowDragging: false,
          onSquareClick,
          squareStyles: styles,
          arrows,
          id: 'test-board',
        }} />
      </div>
      {step === 'tap' ? (
        <div className="feedback">
          <p><strong>1. A question first. This is not your move yet.</strong> {askWhat}</p>
          {note && <p className="fb-wrong">{note}</p>}
          <div className="controls">
            <button className={tap === NO_THREAT ? 'on' : ''} onClick={() => { setNote(null); setTap(tap === NO_THREAT ? null : NO_THREAT) }}>
              No immediate threat
            </button>
            <button disabled={!tap} onClick={() => { setNote(null); setStep('move') }}>Next: make your move</button>
          </div>
          {tap && <p>Your answer: {tapWords(tap)}.</p>}
        </div>
      ) : (
        <div className="feedback">
          <p><strong>2. Your move.</strong> Click a piece, then the square it should go to. To castle, click your king,
            then the rook.</p>
          {note && <p className="fb-wrong">{note}</p>}
          <p>Your answer: {tapWords(tap ?? NO_THREAT)}. {move ? `Your move: ${move.slice(0, 2)} to ${move.slice(2, 4)}.` : ''}</p>
          <div className="controls">
            <button disabled={busy} onClick={() => { setStep('tap'); setFrom(null); setMove(null); setNote(null) }}>Back</button>
            <button disabled={!move || busy} onClick={send}>{busy ? 'Saving…' : 'Submit this position'}</button>
          </div>
          <p className="note small">A submitted position cannot be changed.</p>
        </div>
      )}
    </div>
  )
}

function ResultsPage({ id, onBack }: { id: number; onBack: () => void }) {
  const [res, setRes] = useState<Results | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let stop = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const fetchOnce = () => {
      api<Results>(`/coach/assessments/${id}/results`)
        .then((r) => {
          if (stop) return
          setRes(r)
          if (r.chance_pending) timer = setTimeout(fetchOnce, RESULTS_POLL_MS)
        })
        .catch((e: Error) => !stop && setError(e.message))
    }
    fetchOnce()
    return () => {
      stop = true
      if (timer) clearTimeout(timer)
    }
  }, [id])

  if (error) return <div className="app"><p className="error">{error}</p></div>
  if (!res) return <div className="app"><p>Loading…</p></div>
  return (
    <div className="spots">
      <button onClick={onBack}>Back</button>
      <h2>{res.label}: your starting test</h2>
      <div className="card">
        <p className="headline">Spotted the problem: {scoreLine(res.scores.recognition, res.total, res.chance.recognition)}</p>
        <p className="headline">Played a sound move: {scoreLine(res.scores.move, res.total, res.chance.move)}</p>
        <p className="headline">Both right: {scoreLine(res.scores.combined, res.total, res.chance.combined)}</p>
        {scoreNotes(res).map((n) => <p key={n} className="note fb-wrong">{n}</p>)}
        <p className="note small">
          "Guessing" is how many a random tap and a random legal move would get right on these same positions. Five
          positions is a small sample: this is a starting point, not a verdict.
          {res.chance_pending && ' The guessing number for moves takes about a minute to calculate.'}
          {res.interrupted > 0 && ` ${res.interrupted} position(s) were interrupted (left and resumed).`}
        </p>
      </div>
      {res.items.map((it) => <ResultCard key={it.number} item={it} />)}
    </div>
  )
}

function ResultCard({ item }: { item: ResultItem }) {
  const styles: Record<string, React.CSSProperties> = {}
  const own = pieceColorAt(item.fen, item.answer_squares[0] ?? '') === (item.side_to_move === 'white' ? 'w' : 'b')
  for (const sq of item.answer_squares) styles[sq] = { background: own ? 'rgba(220, 60, 50, 0.6)' : 'rgba(60, 170, 90, 0.6)' }
  if (item.your_tap !== NO_THREAT) styles[item.your_tap] = { ...styles[item.your_tap], boxShadow: 'inset 0 0 0 4px rgba(80, 140, 230, 0.9)' }
  const good = item.good_moves[0]
  const arrows = [
    { startSquare: item.your_move.uci.slice(0, 2), endSquare: item.your_move.uci.slice(2, 4), color: 'rgba(80, 140, 230, 0.8)' },
    ...(good && good.uci !== item.your_move.uci
      ? [{ startSquare: good.uci.slice(0, 2), endSquare: good.uci.slice(2, 4), color: 'rgba(60, 170, 90, 0.85)' }]
      : []),
  ]
  return (
    <div className={`feedback ${item.correct ? 'good' : 'mistake'}`}>
      <p><strong>Position {item.number}</strong>{item.seconds !== null && ` · ${item.seconds} s`}{item.interrupted && ' · interrupted'}</p>
      <div className="moment-board">
        <Chessboard options={{ position: item.fen, boardOrientation: item.side_to_move, allowDragging: false, squareStyles: styles,
          arrows, id: `result-${item.number}` }} />
      </div>
      <p className={item.tap_correct ? 'fb-right' : 'fb-wrong'}>
        You chose {tapWords(item.your_tap)}: {item.tap_correct ? 'right' : 'not right'}.
      </p>
      <p>{item.explanation}</p>
      <p className={item.move_sound ? 'fb-right' : 'fb-wrong'}>{item.move_explanation}</p>
      {!item.move_sound && good && <p>A good move here: {good.san} (green arrow).</p>}
      <p className="note small">Blue: your tap and your move. {item.answer_squares.length > 0 && (own ? 'Red: your piece in danger.' : 'Green square: the free piece.')}</p>
    </div>
  )
}

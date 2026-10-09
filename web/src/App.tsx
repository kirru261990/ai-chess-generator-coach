import { useCallback, useEffect, useRef, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import './App.css'
import EvalBar from './EvalBar'
import { evalIsCurrent, type Evaluation } from './evaluation'
import {
  acceptGame,
  boardMarks,
  isUndoKey,
  moveBadge,
  feedbackIsCurrent,
  feedbackToShow,
  latestUserPly,
  feedbackKey,
  storeFeedback,
  whyLabel,
  type Why,
  threatsAreCurrent,
  type Threats,
  type Feedback,
  type StoredFeedback,
  type GameView,
} from './gameState'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
// The engine answers in ~0.2 s, which is too fast for the player to follow what happened.
// Show its reply no sooner than this after the player's move.
const ENGINE_MIN_REPLY_MS = 1000
const LEVELS = Array.from({ length: 10 }, (_, i) => i + 1)

export default function App() {
  const [game, setGame] = useState<GameView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [engineFailed, setEngineFailed] = useState(false)
  const [color, setColor] = useState<'white' | 'black'>('white')
  const [level, setLevel] = useState(3)
  const [mode, setMode] = useState<'play' | 'practice'>('play')
  const engineInFlight = useRef(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<StoredFeedback | null>(null)
  const [showArrow, setShowArrow] = useState(false) // never proactive: only when the player asks with the hint icon
  const [evaluation, setEvaluation] = useState<(Evaluation & { gameId: string }) | null>(null)
  const askedEval = useRef('')
  const evalRetries = useRef(0)
  const [evalRetry, setEvalRetry] = useState(0)
  const asked = useRef('')
  const [why, setWhy] = useState<{ key: string; loading: boolean; data: Why | null } | null>(null)
  const [threats, setThreats] = useState<(Threats & { gameId: string }) | null>(null)
  const askedThreats = useRef('')

  // Responses can arrive out of order (the engine's reply is shown after a delay), so an
  // older snapshot must never replace a newer one or one for a game that was left behind.
  const applyGame = useCallback((g: GameView) => setGame((current) => acceptGame(current, g)), [])

  const call = useCallback(async (path: string, body?: object): Promise<GameView | null> => {
    try {
      const res = await fetch(`${API}${path}`, {
        method: body ? 'POST' : 'GET',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.message ?? data.error ?? `Request failed (${res.status})`)
        return null
      }
      setError(null)
      return data as GameView
    } catch {
      setError('Cannot reach the API. Is the backend running on port 8000?')
      return null
    }
  }, [])

  async function newGame() {
    setBusy(true)
    setEngineFailed(false)
    const g = await call('/games', { color, mode, level })
    setBusy(false)
    if (g) setGame((current) => acceptGame(current, g, true)) // a new game takes over the screen
  }

  useEffect(() => {
    void newGame()
  }, [])

  useEffect(() => {
    setSelected(null)
  }, [game?.id, game?.revision])

  // Practice only: after each move of mine, ask what was right or wrong. The verdict is shown after the move.
  useEffect(() => {
    if (!game || game.mode !== 'practice') return
    const ply = latestUserPly(game.moves, game.user_color)
    if (ply === null) return
    const moves = game.moves
    const key = `${game.id}:${moves.slice(0, ply + 1).join(' ')}`
    if (asked.current === key) return
    asked.current = key
    fetch(`${API}/games/${game.id}/feedback/${ply}`)
      .then(async (res) => (res.ok ? ((await res.json()) as Feedback) : null))
      .then((fb) => {
        if (fb && asked.current === key) {
          setFeedback(storeFeedback(fb, game.id, moves))
        }
      })
      .catch(() => {})
  }, [game])

  // Practice only: when it is my turn, warn about what the opponent threatens right now.
  useEffect(() => {
    if (!game || game.mode !== 'practice' || game.outcome || game.turn !== game.user_color) return
    const key = `${game.id}:${game.revision}`
    if (askedThreats.current === key) return
    askedThreats.current = key
    fetch(`${API}/games/${game.id}/threats`)
      .then(async (res) => (res.ok ? ((await res.json()) as Threats) : null))
      .then((t) => {
        if (t && askedThreats.current === key) setThreats({ ...t, gameId: game.id })
      })
      .catch(() => {})
  }, [game])

  // Practice only: the evaluation bar follows the position after every move, mine and the opponent's.
  useEffect(() => {
    if (!game || game.mode !== 'practice') return
    const key = `${game.id}:${game.revision}`
    if (askedEval.current === key) return
    askedEval.current = key
    const failed = () => {
      // Allow one more try a little later; the bar shows "unavailable" meanwhile, never an older position's score.
      if (askedEval.current !== key) return
      askedEval.current = ''
      if (evalRetries.current < 2) {
        evalRetries.current += 1
        setTimeout(() => setEvalRetry((n) => n + 1), 3000)
      }
    }
    fetch(`${API}/games/${game.id}/eval`)
      .then(async (res) => (res.ok ? ((await res.json()) as Evaluation) : null))
      .then((ev) => {
        if (ev && askedEval.current === key) {
          evalRetries.current = 0
          setEvaluation({ ...ev, gameId: game.id })
        } else if (!ev) failed()
      })
      .catch(failed)
  }, [game, evalRetry])

  // The hint belongs to one judged move. Hide it whenever that changes (new move, takeback, new game), whether or not a
  // fresh verdict has arrived yet, so replaying the same move after Undo never shows it without a new click.
  const judgedKey = game && feedbackIsCurrent(feedback, game.id, game.moves, game.user_color) ? feedbackKey(feedback) : null
  useEffect(() => {
    setShowArrow(false)
  }, [judgedKey])

  const engineToMove =
    !!game && !game.outcome && game.engine_level !== null && game.turn !== game.user_color

  // Whenever it is the engine's turn, ask the server for its move. The server
  // call is idempotent, so a retry can never play two moves.
  useEffect(() => {
    if (!game || !engineToMove || busy || engineFailed || engineInFlight.current) return
    engineInFlight.current = true
    setBusy(true)
    const started = Date.now()
    void call(`/games/${game.id}/engine-move`, {}).then(async (g) => {
      const wait = ENGINE_MIN_REPLY_MS - (Date.now() - started)
      if (g && wait > 0) await new Promise((resolve) => setTimeout(resolve, wait))
      engineInFlight.current = false
      setBusy(false)
      if (g) applyGame(g)
      else setEngineFailed(true)
    })
  }, [game, engineToMove, busy, engineFailed, call, applyGame])

  // Click a piece, then click where it should go. The board only ever shows the
  // server-confirmed position; legal targets come from the server's list.
  function onSquareClick({ piece, square }: { piece: { pieceType: string } | null; square: string }) {
    if (!game || game.outcome || busy || engineToMove || previewing) return
    const mine = piece !== null && piece.pieceType[0] === (game.user_color === 'white' ? 'w' : 'b')
    if (mine) {
      setSelected(square === selected ? null : square)
      return
    }
    if (!selected) return
    const candidates = game.legal_moves.filter((m) => m.startsWith(selected + square))
    if (candidates.length === 0) {
      setSelected(null) // not a legal target: clear the selection
      return
    }
    const uci = candidates.find((m) => m.endsWith('q')) ?? candidates[0] // auto-queen
    setSelected(null)
    setBusy(true)
    void call(`/games/${game.id}/moves`, {
      uci,
      expected_revision: game.revision,
      engine_reply: false, // show my move now; the engine's reply follows
    }).then((g) => {
      setBusy(false)
      if (g) applyGame(g)
    })
  }

  const highlights: Record<string, React.CSSProperties> = {}
  const fb = game ? feedbackToShow(feedback, game) : null // Practice only: nothing here may leak into Play
  // The hint switches the main board to the position BEFORE the player's last move, with the stronger move drawn on it.
  // That is the only position the suggestion is valid for. Nothing can be played while it is showing.
  const previewing = !!(fb?.better_move && showArrow)
  const warn = game && threats && threatsAreCurrent(threats, game) ? threats : null
  if (warn) {
    for (const t of warn.threats) {
      if (t.square) highlights[t.square] = { background: 'rgba(220, 60, 50, 0.45)' }
    }
  }
  // After a suboptimal move: mark on the board your piece(s) that can be taken (red) and a free piece you missed (green).
  const marks = game && fb ? boardMarks(game.fen, fb) : { hanging: [], missed: [] }
  for (const sq of marks.hanging) highlights[sq] = { background: 'rgba(220, 60, 50, 0.6)' }
  for (const sq of marks.missed) highlights[sq] = { background: 'rgba(60, 170, 90, 0.6)' }
  // The badge for the player's last move, drawn on the square it was played to (never on the hint view of the old position).
  const badge = fb && !previewing ? moveBadge(fb.classification.key, fb.classification.opening) : null
  const badgeSquare = fb ? fb.played.uci.slice(2, 4) : null
  // The board library skips its own square styling when a custom square renderer returns something, so the renderer must
  // apply the square styles itself (the move dots, the red and green marks, the hint tint). `boardStyles` is the one source.
  const boardStyles: Record<string, React.CSSProperties> =
    previewing && fb?.better_move
      ? {
          [fb.better_move.from]: { background: 'rgba(60, 170, 90, 0.35)' },
          [fb.better_move.to]: { background: 'rgba(60, 170, 90, 0.35)' },
        }
      : highlights
  const squareRenderer = ({ square, children }: { square: string; children?: React.ReactNode }) => (
    <div style={{ position: 'relative', width: '100%', height: '100%', ...boardStyles[square] }}>
      {children}
      {badge && square === badgeSquare && (
        <span className={`move-badge ${badge.tone}`} title={badge.label} aria-label={badge.label}>
          {badge.symbol}
        </span>
      )}
    </div>
  )
  // A suggestion only: nothing stops the player from playing anything. It was computed for the position before the
  // player's move, so it is drawn on that saved position, never on the live board.
  const hintArrows = fb?.better_move
    ? [{ startSquare: fb.better_move.from, endSquare: fb.better_move.to, color: 'rgba(60, 170, 90, 0.85)' }]
    : []
  if (game && selected) {
    highlights[selected] = { background: 'rgba(255, 215, 0, 0.55)' }
    for (const m of game.legal_moves) {
      if (m.startsWith(selected)) {
        highlights[m.slice(2, 4)] = {
          background: 'radial-gradient(circle, rgba(0,0,0,0.28) 22%, transparent 24%)',
        }
      }
    }
  }

  async function switchMode(next: 'play' | 'practice') {
    if (!game || game.outcome || next === game.mode) return
    if (
      next === 'practice' &&
      !window.confirm(
        'Switch to Practice? This game will be marked assisted permanently, even if you switch back.',
      )
    )
      return
    setShowArrow(false) // leave the hint view whenever the mode changes
    const g = await call(`/games/${game.id}/mode`, { mode: next })
    if (g) applyGame(g)
  }

  async function askWhy(f: StoredFeedback) {
    const key = feedbackKey(f)
    setWhy({ key, loading: true, data: null })
    try {
      const res = await fetch(`${API}/games/${f.gameId}/coach/why`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ply: f.ply }),
      })
      const data = res.ok ? ((await res.json()) as Why) : null
      setWhy((cur) => (cur?.key === key ? { key, loading: false, data } : cur))
    } catch {
      setWhy((cur) => (cur?.key === key ? { key, loading: false, data: null } : cur))
    }
  }

  async function undo() {
    if (!game || busy) return
    setEngineFailed(false)
    setShowArrow(false)
    const g = await call(`/games/${game.id}/takeback`, {})
    if (g) applyGame(g)
  }

  // Esc leaves the hint view and returns to the live game.
  useEffect(() => {
    function onEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') setShowArrow(false)
    }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [])

  // Left arrow = Undo (Practice only, and not while typing in a box or choosing in a menu).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null
      if (!isUndoKey(e, el?.tagName ?? '', !!el?.isContentEditable)) return
      if (!game || game.mode !== 'practice' || !game.can_take_back || busy) return
      e.preventDefault()
      void undo()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  async function resign() {
    if (!game || game.outcome) return
    const g = await call(`/games/${game.id}/resign`, {})
    if (g) applyGame(g)
  }

  const status = !game
    ? ''
    : game.outcome
      ? `Game over: ${game.outcome.result} (${game.outcome.termination})`
      : engineToMove
        ? `Stockfish Level ${game.engine_level} is thinking…`
        : 'Your move'

  return (
    <main className="app">
      <h1>AI Chess Coach</h1>
      <div className="controls">
        <label>
          Play as{' '}
          <select value={color} onChange={(e) => setColor(e.target.value as 'white' | 'black')}>
            <option value="white">White</option>
            <option value="black">Black</option>
          </select>
        </label>
        <label>
          Mode{' '}
          <select value={mode} onChange={(e) => setMode(e.target.value as 'play' | 'practice')}>
            <option value="play">Play</option>
            <option value="practice">Practice (assisted)</option>
          </select>
        </label>
        <label>
          Level{' '}
          <select value={level} onChange={(e) => setLevel(Number(e.target.value))}>
            {LEVELS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <button onClick={() => void newGame()} disabled={busy}>
          New game
        </button>
      </div>
      {game && (
        <>
          {previewing && (
            <p className="preview-banner" role="status">
              Showing the position before your last move. The green arrow is a stronger move: only a suggestion, play what you
              like. <button onClick={() => setShowArrow(false)}>Back to my game</button> (or press Esc)
            </p>
          )}
          <div className="board-row">
            {game.mode === 'practice' && (
              <EvalBar
                evaluation={evalIsCurrent(evaluation, game.id, game.revision) ? evaluation : null} // pending until this position's score arrives
                orientation={game.user_color}
              />
            )}
            <div className="board">
            <Chessboard
              options={{
                position: previewing && fb ? fb.fen_before : game.fen,
                boardOrientation: game.user_color,
                allowDragging: false,
                onSquareClick,
                squareStyles: boardStyles,
                arrows: previewing ? hintArrows : [],
                squareRenderer,
                id: 'main-board',
              }}
            />
            </div>
          </div>
          {game.mode === 'practice' && (
            <section className={`feedback ${fb ? fb.verdict : ''}`} aria-live="polite">
              {fb ? (
                <>
                  <p className="fb-head">
                    <strong>{moveBadge(fb.classification.key, fb.classification.opening).symbol} {fb.headline}</strong> <span className="fb-move">You played {fb.played.text}.</span>
                  </p>
                  {fb.right.map((t) => (
                    <p key={t} className="fb-right">✓ {t}</p>
                  ))}
                  {fb.wrong.map((t) => (
                    <p key={t} className="fb-wrong">✗ {t}</p>
                  ))}
                  {(marks.hanging.length > 0 || marks.missed.length > 0) && (
                    <p className="fb-legend">
                      {marks.hanging.length > 0 && <span><i className="sw red" /> your piece that can be taken (or was taken here) </span>}
                      {marks.missed.length > 0 && <span><i className="sw green" /> a free piece you could have taken</span>}
                    </p>
                  )}
                  {(() => {
                    const mine = why && why.key === feedbackKey(fb) ? why : null
                    if (mine?.loading) return <p className="fb-wait">Checking the explanation…</p>
                    if (mine?.data)
                      return (
                        <div className="why">
                          <p>{mine.data.text}</p>
                          <p className="fb-wait">{mine.data.note ?? whyLabel(mine.data.status)}</p>
                        </div>
                      )
                    return (
                      <button onClick={() => void askWhy(fb)}>
                        {mine ? 'Could not load it. Try again' : 'Why?'}
                      </button>
                    )
                  })()}{' '}
                  {fb.better_move && (
                    <button
                      className={`hint ${showArrow ? 'on' : ''}`}
                      onClick={() => setShowArrow((v) => !v)}
                      aria-pressed={showArrow}
                      aria-label="Hint: show what could have been the best move"
                      title="Hint: what could have been the best move?"
                    >
                      💡
                    </button>
                  )}
                </>
              ) : (
                <p className="fb-wait">Make a move and I will tell you what was right or wrong with it.</p>
              )}
            </section>
          )}
          {game.mode === 'practice' && warn && (warn.in_check || warn.threats.length > 0) && (
            <section className="threats" aria-live="polite">
              <strong>Watch out</strong>
              {warn.in_check && <p>You are in check.</p>}
              {warn.threats.map((t) => (
                <p key={t.text}>⚠ {t.text}</p>
              ))}
            </section>
          )}
          <p>
            {status} · {game.mode === 'play' ? 'Play' : 'Practice'}
            {game.assisted && <span className="badge"> assisted</span>}
          </p>
          <div className="controls">
            <button
              onClick={() => void switchMode(game.mode === 'play' ? 'practice' : 'play')}
              disabled={!!game.outcome}
            >
              {game.mode === 'play' ? 'Switch to Practice' : 'Switch to Play'}
            </button>
            {game.mode === 'practice' && (
              <button onClick={() => void undo()} disabled={busy || !game.can_take_back} title="Undo (left arrow key)">
                Undo
              </button>
            )}
            <button onClick={() => void resign()} disabled={!!game.outcome}>
              Resign
            </button>
            <a href={`${API}/games/${game.id}/pgn`} download={`game-${game.id.slice(0, 8)}.pgn`}>
              Download PGN
            </a>
          </div>
        </>
      )}
      {error && (
        <p role="alert" className="error">
          {error}{' '}
          {engineFailed && (
            <button onClick={() => setEngineFailed(false)}>Retry opponent move</button>
          )}
        </p>
      )}
    </main>
  )
}

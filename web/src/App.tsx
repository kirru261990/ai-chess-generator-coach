import { useCallback, useEffect, useRef, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import './App.css'
import {
  acceptGame,
  feedbackIsCurrent,
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
  const [showBetter, setShowBetter] = useState(false)
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
          setShowBetter(false)
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
    if (!game || game.outcome || busy || engineToMove) return
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
  const fb = game && feedbackIsCurrent(feedback, game.id, game.moves, game.user_color) ? feedback : null
  const warn = game && threats && threatsAreCurrent(threats, game) ? threats : null
  if (warn) {
    for (const t of warn.threats) {
      if (t.square) highlights[t.square] = { background: 'rgba(220, 60, 50, 0.45)' }
    }
  }
  if (fb && showBetter && fb.better_move) {
    highlights[fb.better_move.from] = { background: 'rgba(60, 170, 90, 0.55)' }
    highlights[fb.better_move.to] = { background: 'rgba(60, 170, 90, 0.55)' }
  }
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
    const g = await call(`/games/${game.id}/takeback`, {})
    if (g) applyGame(g)
  }

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
          <div className="board">
            <Chessboard
              options={{
                position: game.fen,
                boardOrientation: game.user_color,
                allowDragging: false,
                onSquareClick,
                squareStyles: highlights,
                id: 'main-board',
              }}
            />
          </div>
          {game.mode === 'practice' && (
            <section className={`feedback ${fb ? fb.verdict : ''}`} aria-live="polite">
              {fb ? (
                <>
                  <p className="fb-head">
                    <strong>{fb.headline}</strong> <span className="fb-move">You played {fb.played.text}.</span>
                  </p>
                  {fb.right.map((t) => (
                    <p key={t} className="fb-right">✓ {t}</p>
                  ))}
                  {fb.wrong.map((t) => (
                    <p key={t} className="fb-wrong">✗ {t}</p>
                  ))}
                  {fb.cost_pawns !== null && fb.cost_pawns > 0 && (
                    <p className="fb-cost">This cost you about {fb.cost_pawns} pawns of advantage.</p>
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
                  {fb.better_move &&
                    (showBetter ? (
                      <p>Better was: <strong>{fb.better_move.text}</strong> (shown in green on the board)</p>
                    ) : (
                      <button onClick={() => setShowBetter(true)}>Show the better move</button>
                    ))}
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
              <button onClick={() => void undo()} disabled={busy || game.takebacks_left === 0}>
                Undo ({game.takebacks_left} left)
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

import { useCallback, useEffect, useRef, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import './App.css'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const LEVELS = Array.from({ length: 10 }, (_, i) => i + 1)

type GameView = {
  id: string
  fen: string
  revision: number
  turn: 'white' | 'black'
  user_color: 'white' | 'black'
  mode: string
  assisted: boolean
  engine_level: number | null
  outcome: { result: string; termination: string } | null
  legal_moves: string[]
  moves: string[]
  takebacks_left: number
}

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
    if (g) setGame(g)
  }

  useEffect(() => {
    void newGame()
  }, [])

  useEffect(() => {
    setSelected(null)
  }, [game?.id, game?.revision])

  const engineToMove =
    !!game && !game.outcome && game.engine_level !== null && game.turn !== game.user_color

  // Whenever it is the engine's turn, ask the server for its move. The server
  // call is idempotent, so a retry can never play two moves.
  useEffect(() => {
    if (!game || !engineToMove || busy || engineFailed || engineInFlight.current) return
    engineInFlight.current = true
    setBusy(true)
    void call(`/games/${game.id}/engine-move`, {}).then((g) => {
      engineInFlight.current = false
      setBusy(false)
      if (g) setGame(g)
      else setEngineFailed(true)
    })
  }, [game, engineToMove, busy, engineFailed, call])

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
      if (g) setGame(g)
    })
  }

  const highlights: Record<string, React.CSSProperties> = {}
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
    if (g) setGame(g)
  }

  async function undo() {
    if (!game || busy) return
    setEngineFailed(false)
    const g = await call(`/games/${game.id}/takeback`, {})
    if (g) setGame(g)
  }

  async function resign() {
    if (!game || game.outcome) return
    const g = await call(`/games/${game.id}/resign`, {})
    if (g) setGame(g)
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

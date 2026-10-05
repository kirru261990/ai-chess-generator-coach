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
}

export default function App() {
  const [game, setGame] = useState<GameView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [engineFailed, setEngineFailed] = useState(false)
  const [color, setColor] = useState<'white' | 'black'>('white')
  const [level, setLevel] = useState(3)
  const engineInFlight = useRef(false)

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
    const g = await call('/games', { color, mode: 'play', level })
    setBusy(false)
    if (g) setGame(g)
  }

  useEffect(() => {
    void newGame()
  }, [])

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

  // The board only ever shows the server-confirmed position: a drop sends the
  // move to the API and returns false, so a rejected move snaps back.
  function onDrop({
    piece,
    sourceSquare,
    targetSquare,
  }: {
    piece: { pieceType: string }
    sourceSquare: string
    targetSquare: string | null
  }): boolean {
    if (!game || !targetSquare || game.outcome || busy || engineToMove) return false
    const isPawn = piece.pieceType[1] === 'P'
    const promo = isPawn && (targetSquare[1] === '8' || targetSquare[1] === '1') ? 'q' : ''
    setBusy(true)
    void call(`/games/${game.id}/moves`, {
      uci: sourceSquare + targetSquare + promo,
      expected_revision: game.revision,
      engine_reply: false, // show my move now; the engine's reply follows
    }).then((g) => {
      setBusy(false)
      if (g) setGame(g)
    })
    return false
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
                onPieceDrop: onDrop,
                id: 'main-board',
              }}
            />
          </div>
          <p>
            {status} · {game.mode}
            {game.assisted && ' · assisted'}
          </p>
          <div className="controls">
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

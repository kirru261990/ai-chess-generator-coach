import { useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import './App.css'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type GameView = {
  id: string
  fen: string
  revision: number
  turn: 'white' | 'black'
  user_color: 'white' | 'black'
  mode: string
  assisted: boolean
  outcome: { result: string; termination: string } | null
}

export default function App() {
  const [game, setGame] = useState<GameView | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function call(path: string, body?: object): Promise<GameView | null> {
    try {
      const res = await fetch(`${API}${path}`, {
        method: body ? 'POST' : 'GET',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.message ?? data.error)
        return null
      }
      setError(null)
      return data as GameView
    } catch {
      setError('Cannot reach the API. Is the backend running on port 8000?')
      return null
    }
  }

  async function newGame() {
    const g = await call('/games', { color: 'white', mode: 'play' })
    if (g) setGame(g)
  }

  useEffect(() => {
    void newGame()
  }, [])

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
    if (!game || !targetSquare || game.outcome) return false
    const isPawn = piece.pieceType[1] === 'P'
    const promo = isPawn && (targetSquare[1] === '8' || targetSquare[1] === '1') ? 'q' : ''
    void call(`/games/${game.id}/moves`, {
      uci: sourceSquare + targetSquare + promo,
      expected_revision: game.revision,
    }).then((g) => g && setGame(g))
    return false
  }

  return (
    <main className="app">
      <h1>AI Chess Coach</h1>
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
            {game.outcome
              ? `Game over: ${game.outcome.result} (${game.outcome.termination})`
              : `${game.turn} to move`}{' '}
            · mode: {game.mode}
            {game.assisted && ' · assisted'}
          </p>
        </>
      )}
      {error && <p role="alert" className="error">{error}</p>}
      <button onClick={() => void newGame()}>New game</button>
    </main>
  )
}

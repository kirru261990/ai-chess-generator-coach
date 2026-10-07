import { useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { gameLabel, intentMessage, type IntentResult, type Review, type SyncedGame } from './reviewMoments'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function api<T>(path: string, body?: object): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message ?? `Request failed (${res.status})`)
  return data as T
}

export default function ReviewPage() {
  const [games, setGames] = useState<SyncedGame[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [review, setReview] = useState<Review | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api<SyncedGame[]>('/synced-games?limit=20')
      .then(setGames)
      .catch((e: Error) => setError(e.message))
  }, [])

  async function open(id: string) {
    setLoading(true)
    setError(null)
    setReview(null)
    try {
      setReview(await api<Review>(`/synced-games/${id}/review`))
    } catch (e) {
      setError((e as Error).message)
    }
    setLoading(false)
  }

  return (
    <section className="spots">
      <h2>Review a game</h2>
      <p className="note">
        Pick a game. I show up to three moments that cost you the most. You can say what you were thinking at each one;
        it is optional, and your words are saved exactly as you wrote them.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!games && !error && <p>Loading…</p>}
      {games && (
        <ul className="game-list">
          {games.map((g) => (
            <li key={g.game_id}>
              <button onClick={() => void open(g.game_id)} disabled={loading}>
                {gameLabel(g)}
              </button>
            </li>
          ))}
        </ul>
      )}
      {loading && <p>Checking the game with the engine… this takes a few seconds.</p>}
      {review && (
        <div>
          <h3>
            vs {review.opponent} · {review.result}
          </h3>
          {review.moments.length === 0 && <p>No big mistakes found in this game.</p>}
          {review.moments.map((m) => (
            <MomentCard key={m.ply} gameId={review.game_id} color={review.user_color} moment={m} />
          ))}
        </div>
      )}
    </section>
  )
}

function MomentCard({
  gameId,
  color,
  moment,
}: {
  gameId: string
  color: 'white' | 'black'
  moment: Review['moments'][number]
}) {
  const [text, setText] = useState('')
  const [result, setResult] = useState<IntentResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(skip: boolean) {
    setBusy(true)
    setError(null)
    try {
      setResult(
        await api<IntentResult>(`/synced-games/${gameId}/moments/${moment.ply}/intent`, {
          text: skip ? null : text,
        }),
      )
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(false)
  }

  return (
    <article className="card moment">
      <strong>Move {moment.move_number}</strong>
      <div className="moment-board">
        <Chessboard
          options={{
            position: moment.fen_before,
            boardOrientation: color,
            allowDragging: false,
            id: `moment-${moment.ply}`,
          }}
        />
      </div>
      <p>{moment.takeaway}</p>
      {!result ? (
        <>
          <label>
            What were you considering? (optional)
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="For example: I wanted to attack the knight"
            />
          </label>
          <div className="controls">
            <button onClick={() => void submit(false)} disabled={busy || text.trim() === ''}>
              Compare with the board
            </button>
            <button onClick={() => void submit(true)} disabled={busy}>
              Skip
            </button>
          </div>
        </>
      ) : (
        <div className="why">
          {result.answer && <p>You said: “{result.answer}”</p>}
          {intentMessage(result).map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </article>
  )
}

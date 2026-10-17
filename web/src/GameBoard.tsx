import { useEffect, useMemo, useRef, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { practiceOnly, toGameView, toHint, type GameBackend, type GamePayload } from './gameBackend'
import {
  boardMarks, feedbackToShow, gameEndBanner, hintToShow, moveBadge, storeFeedback, threatArrows, threatsAreCurrent,
  type Hint,
} from './gameState'

const HINT_STEPS = ['Think', 'Idea', 'Piece', 'Why', 'Move'] // one per server step (spec D4)
const ENGINE_MIN_REPLY_MS = 1000 // as in the web app: the player's move stays on the board alone for this long before the reply
const DOT = 'radial-gradient(circle, rgba(0,0,0,0.28) 22%, transparent 24%)'

/** A game against Stockfish inside the chat (ADR 0009). Play shows the board, a status line and Resign, nothing else: every helper below
 *  reads from `practiceOnly(payload)`, which is null in Play. The server plays the engine's reply inside the move call. */
export default function GameBoard({ initial, backend }: { initial: GamePayload; backend: GameBackend }) {
  const [payload, setPayload] = useState(initial)
  const [hint, setHint] = useState<Hint | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null) // what the server is doing, for the status line
  const [error, setError] = useState<string | null>(null)

  // The host can show a newer result for the same game (the chat model called a tool): take it unless it is older.
  useEffect(() => {
    setPayload((cur) => (initial.game.id !== cur.game.id || initial.game.revision >= cur.game.revision ? initial : cur))
    const h = toHint(initial)
    if (h) setHint(h)
  }, [initial])

  const game = useMemo(() => toGameView(payload), [payload])
  const extras = practiceOnly(payload) // null in Play: the only door to any help
  const practice = extras !== null
  useEffect(() => setSelected(null), [game.id, game.revision])

  const accept = (next: GamePayload) => {
    setPayload((cur) => (next.game.id === cur.game.id && next.game.revision < cur.game.revision ? cur : next))
    const h = toHint(next)
    if (h) setHint(h)
  }

  async function step(label: string, fn: () => Promise<GamePayload>) {
    if (busy) return
    setBusy(label)
    setError(null)
    try {
      accept(await fn())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const myTurn = !game.outcome && game.turn === game.user_color
  function onSquareClick({ piece, square }: { piece: { pieceType: string } | null; square: string }) {
    if (!myTurn || busy) return
    if (piece !== null && piece.pieceType[0] === (game.user_color === 'white' ? 'w' : 'b')) {
      setSelected(square === selected ? null : square)
      return
    }
    if (!selected) return
    const candidates = game.legal_moves.filter((m) => m.startsWith(selected + square))
    if (candidates.length === 0) return setSelected(null)
    const uci = candidates.find((m) => m.endsWith('q')) ?? candidates[0] // auto-queen
    setSelected(null)
    void step('Sending your move…', async () => {
      const first = await backend.move(game.id, uci, game.revision) // the player's move, at once
      accept(first)
      if (first.game.outcome || first.game.turn === first.game.user_color) return first
      setBusy('Stockfish is thinking…')
      const shown = Date.now()
      const reply = await backend.engineMove(first.game.id, first.game.revision) // then the reply, no sooner than 1 s later
      const wait = ENGINE_MIN_REPLY_MS - (Date.now() - shown)
      if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait))
      return reply
    })
  }

  // If the engine owes a reply (its search failed after my move was saved), ask once per position; game_show plays it.
  const resumed = useRef('')
  useEffect(() => {
    const key = `${game.id}:${game.revision}`
    if (game.outcome || game.turn === game.user_color || busy || resumed.current === key) return
    resumed.current = key
    void step('Stockfish is thinking…', () => backend.show(game.id))
  })

  // --- Practice only from here: every value is null or empty in Play ---------------------------------------------------
  const fb = extras?.feedback ? feedbackToShow(storeFeedback(extras.feedback, game.id, game.moves), game) : null
  const shownHint = practice && !game.outcome ? hintToShow(hint, game) : null
  const warn = extras?.threats && extras.show_threats && threatsAreCurrent({ ...extras.threats, gameId: game.id }, game) ? extras.threats : null
  const marks = fb ? boardMarks(game.fen, fb) : { hanging: [], missed: [] }
  const badge = fb ? moveBadge(fb.classification.key, fb.classification.opening) : null
  const badgeSquare = fb ? fb.played.uci.slice(2, 4) : null
  const hintFrom = shownHint?.steps.find((s) => s.kind === 'piece')?.from ?? null
  const hintUci = shownHint?.steps.find((s) => s.kind === 'move')?.uci ?? null

  const styles: Record<string, React.CSSProperties> = {}
  const last = game.moves[game.moves.length - 1] // the last move played, by either side (not help: it is the move record)
  if (last) for (const sq of [last.slice(0, 2), last.slice(2, 4)]) styles[sq] = { background: 'rgba(255, 230, 0, 0.3)' }
  for (const t of warn?.threats ?? []) if (t.square) styles[t.square] = { background: 'rgba(220, 60, 50, 0.45)' }
  for (const sq of marks.hanging) styles[sq] = { background: 'rgba(220, 60, 50, 0.6)' }
  for (const sq of marks.missed) styles[sq] = { background: 'rgba(60, 170, 90, 0.6)' }
  if (selected) {
    styles[selected] = { background: 'rgba(255, 215, 0, 0.55)' }
    for (const m of game.legal_moves) if (m.startsWith(selected)) styles[m.slice(2, 4)] = { background: DOT }
  }
  if (hintFrom) {
    for (const m of game.legal_moves) if (m.startsWith(hintFrom)) styles[m.slice(2, 4)] = { background: DOT }
    styles[hintFrom] = { background: 'rgba(60, 170, 90, 0.35)' }
    if (hintUci) styles[hintUci.slice(2, 4)] = { background: 'rgba(60, 170, 90, 0.55)' }
  }
  const arrows = [
    ...(hintUci ? [{ startSquare: hintUci.slice(0, 2), endSquare: hintUci.slice(2, 4), color: 'rgba(60, 170, 90, 0.85)' }] : []),
    ...(warn ? threatArrows(warn) : []),
  ]
  const squareRenderer = ({ square, children }: { square: string; children?: React.ReactNode }) => (
    <div style={{ position: 'relative', width: '100%', height: '100%', ...styles[square] }}>
      {children}
      {badge && square === badgeSquare && (
        <span className={`move-badge ${badge.tone}`} title={badge.label} aria-label={badge.label}>{badge.symbol}</span>
      )}
    </div>
  )

  const end = gameEndBanner(game)
  const status = busy ?? (game.outcome ? `Game over: ${game.outcome.result} (${game.outcome.termination.replace(/_/g, ' ')})` : myTurn ? 'Your move' : 'Stockfish to move')
  const nextLevel = (shownHint?.level ?? 0) + 1

  return (
    <div className="app">
      <div className="board">
        {end && <div className={`mate-banner ${end.celebrate ? 'win' : 'loss'}`} role="status">{end.text}</div>}
        <Chessboard
          options={{
            position: game.fen, boardOrientation: game.user_color, allowDragging: false, onSquareClick,
            squareStyles: styles, arrows, squareRenderer, id: 'game-board',
          }}
        />
      </div>
      <p className="status-line">
        <strong>{status}</strong> · {practice ? 'Practice' : 'Play'} · Stockfish level {game.engine_level}
        {extras?.assisted && <span className="badge"> assisted</span>}
      </p>
      {fb && <p className="fb-wait">{fb.headline}</p>}
      {practice && !game.outcome && (
        <section className="hint-card" aria-live="polite">
          {shownHint && (
            <ul className="hint-steps">
              {shownHint.steps.map((s) => (
                <li key={s.level}><b>{HINT_STEPS[s.level - 1]}:</b> {s.text}</li>
              ))}
            </ul>
          )}
          <div className="hint-actions">
            {nextLevel <= HINT_STEPS.length && (
              <button className="primary" disabled={!!busy || !myTurn} onClick={() => void step('Thinking…', () => backend.hint(game.id, nextLevel))}>
                {shownHint ? `Show step ${nextLevel}: ${HINT_STEPS[nextLevel - 1]}` : '💡 Give me a hint'}
              </button>
            )}
            {shownHint && <button onClick={() => setHint(null)}>Hide</button>}
          </div>
        </section>
      )}
      <div className="controls">
        {practice && (
          <label className="threat-toggle" title="Draw the pieces the opponent can win as red arrows">
            <input
              type="checkbox" checked={extras.show_threats} disabled={!!busy}
              onChange={(e) => void step('Updating…', () => backend.threats(game.id, e.target.checked))}
            /> Show threats
          </label>
        )}
        {practice && (
          <button disabled={!!busy || !extras.can_take_back} onClick={() => void step('Taking back…', () => backend.undo(game.id))}>Undo</button>
        )}
        <button disabled={!!busy || !!game.outcome} onClick={() => void step('Resigning…', () => backend.resign(game.id))}>Resign</button>
      </div>
      {error && <p role="alert" className="error">{error}</p>}
    </div>
  )
}

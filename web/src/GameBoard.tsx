import { useEffect, useMemo, useRef, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { applyMove } from './applyMove'
import { playMove } from './optimisticMove'
import { practiceOnly, toGameView, toHint, type GameBackend, type GamePayload } from './gameBackend'
import {
  boardMarks, feedbackToShow, gameEndBanner, hintToShow, isUndoKey, moveBadge, opponentLabel, storeFeedback, threatArrows, threatsAreCurrent,
  type Hint,
} from './gameState'

const HINT_STEPS = ['Think', 'Idea', 'Piece', 'Why', 'Move'] // one per server step (spec D4)
const DOT = 'radial-gradient(circle, rgba(0,0,0,0.28) 22%, transparent 24%)'

/** A game against Stockfish inside the chat (ADR 0009). Play shows the board, a status line and Resign, nothing else: every helper below
 *  reads from `practiceOnly(payload)`, which is null in Play. The server plays the engine's reply inside the move call. */
export type Enlarge = { large: boolean; toggle: () => void } // the chat's bigger view; absent when the host has none

export default function GameBoard({ initial, backend, enlarge }: { initial: GamePayload; backend: GameBackend; enlarge?: Enlarge }) {
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

  // The chat can reload this page (the player left the chat and came back) and hands over the result it first showed, which is
  // out of date by then. The server holds the game, so ask it once for the position it is in now; an older answer is ignored.
  useEffect(() => {
    let live = true
    backend.show(initial.game.id).then((p) => live && accept(p), () => undefined)
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [pending, setPending] = useState<string | null>(null) // the player's move drawn before the server has confirmed it
  const game = useMemo(() => {
    const g = toGameView(payload)
    // Display only: the legal move list is empty while waiting, so nothing else can be played, and the server's position replaces this.
    return pending
      ? { ...g, fen: applyMove(g.fen, pending), moves: [...g.moves, pending], turn: g.turn === 'white' ? 'black' as const : 'white' as const, legal_moves: [] }
      : g
  }, [payload, pending])
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
    setBusy('Sending your move…')
    setError(null)
    void playMove(backend, game, uci, {
      pending: setPending, payload: accept, status: setBusy,
    }).then((err) => err && setError(err))
  }

  // If the engine owes a reply (its search failed after my move was saved), ask once per position; game_show plays it.
  const resumed = useRef('')
  useEffect(() => {
    const key = `${game.id}:${game.revision}`
    if (game.outcome || game.turn === game.user_color || busy || resumed.current === key) return
    resumed.current = key
    void step('Stockfish is thinking…', () => backend.show(game.id))
  })

  // Left arrow = Undo (Practice only; not while typing, and not while the server is working), as on the web page.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null
      if (!isUndoKey(e, el?.tagName ?? '', !!el?.isContentEditable)) return
      if (!extras?.can_take_back || busy || pending) return
      e.preventDefault()
      void step('Taking back…', () => backend.undo(game.id))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
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
    <div className={`app${enlarge?.large ? ' app-large' : ''}`}>
      <div className="board">
        {end && <div className={`mate-banner ${end.celebrate ? 'win' : 'loss'}`} role="status">{end.text}</div>}
        <Chessboard
          options={{
            position: game.fen, showAnimations: pending === null, // my own move jumps at once; the reply slides
            boardOrientation: game.user_color, allowDragging: false, onSquareClick,
            squareStyles: styles, arrows, squareRenderer, id: 'game-board',
          }}
        />
      </div>
      <p className="status-line">
        <strong>{status}</strong> · {practice ? 'Practice' : 'Play'} · {opponentLabel(game)}
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
        {enlarge && <button onClick={enlarge.toggle} title="Open the board larger, or back in the chat">{enlarge.large ? '⤡ Smaller' : '⤢ Larger'}</button>}
      </div>
      {error && <p role="alert" className="error">{error}</p>}
    </div>
  )
}

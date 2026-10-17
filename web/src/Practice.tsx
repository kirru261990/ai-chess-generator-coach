import { useCallback, useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { restBackend, type BoardPayload, type PracticeBackend } from './practiceBackend'
import { delayedSummaryLine } from './progressState'
import { NO_THREAT, castleMove, pickMove, pieceColorAt, tapRefusal, tapWords, targetsFrom } from './assessState'
import MoveArrows, { LaneLegend } from './MoveArrows'
import {
  feedbackLanes, feedbackMarks, hintButton, hintMarks, replayKey, replayStep, stepTitle, summaryLines,
  type PracticeSummary, type PracticeView,
} from './practiceState'

type Arrow = { startSquare: string; endSquare: string; color: string }

/** Replay My Mistakes (PRD v2 §6): positions from the player's own games, one at a time. Always assisted. */
export default function Practice({ id, onHome, backend = restBackend, initial }: {
  id: number
  onHome?: () => void // the web app's Back; the chat board has no page to go back to
  backend?: PracticeBackend
  initial?: BoardPayload | null // data the host already holds (the chat shows the tool result it just got)
}) {
  const [view, setView] = useState<PracticeView | null>(null)
  const [summary, setSummary] = useState<PracticeSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tap, setTap] = useState<string | null>(null) // the answer to the question, before it is sent
  const [from, setFrom] = useState<string | null>(null)
  const [move, setMove] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null) // why a click did nothing (rules only, never a hint)
  const [showGame, setShowGame] = useState(false) // the replay of what you played in the game, on request only
  const [step, setStep] = useState(0) // which move of that replay the board shows (0 = the position before your move)

  // A new view from the server resets what the player had picked on the board, except after a hint (`keep`).
  const apply = useCallback((v: PracticeView, keep = false) => {
    setView(v)
    if (!keep) {
      setTap(null)
      setFrom(null)
      setMove(null)
      setNote(null)
      setShowGame(false)
      setStep(0)
    }
    if (v.status === 'completed') {
      backend.summary(v.session_id).then(setSummary).catch((e: Error) => setError(e.message))
    }
  }, [backend])

  // ← and → step the replay of the game line. Capture phase, so this wins over the Play board's left-arrow Undo while it is open.
  const replayLength = view?.current?.feedback?.game_line.uci.length ?? 0
  useEffect(() => {
    if (!showGame) return
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null
      const d = replayKey(e, el?.tagName ?? '', !!el?.isContentEditable)
      if (d === 0) return
      e.preventDefault()
      e.stopImmediatePropagation()
      setStep((s) => Math.max(0, Math.min(replayLength, s + d)))
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [showGame, replayLength])

  useEffect(() => {
    if (initial) {
      if (initial.summary) setSummary(initial.summary)
      apply(initial.view)
      return
    }
    backend.get(id).then((v) => apply(v)).catch((e: Error) => setError(e.message))
  }, [id, apply, backend, initial])

  function send(path: string, body: unknown, keep = false) {
    setBusy(true)
    backend.post(id, path, body as Record<string, unknown>)
      .then((v) => apply(v, keep))
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false))
  }

  if (error) return <div className="app"><p className="error">{error}</p>{onHome ? <button onClick={onHome}>Back</button> : <button onClick={() => setError(null)}>OK</button>}</div>
  if (!view) return <div className="app"><p>Loading…</p></div>
  if (view.status === 'completed') return <SummaryPage summary={summary} onHome={onHome} />
  const cur = view.current
  if (!cur) return <div className="app"><p>Loading…</p></div>

  const mine = cur.side_to_move === 'white' ? 'w' : 'b'
  function onSquareClick({ square }: { square: string }) {
    if (!cur || busy) return
    const color = pieceColorAt(cur.fen, square)
    if (cur.stage === 'recognition') {
      if (!color) return
      const why = tapRefusal(tap, square, cur.tap_squares, view!.mistake_type)
      setNote(why)
      if (!why) setTap(square === tap ? null : square)
      return
    }
    if (cur.stage !== 'move') return
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

  // What is drawn on the board: the hints asked for, the player's picks, or (after the move) the feedback.
  const styles: Record<string, React.CSSProperties> = {}
  let arrows: Arrow[] = []
  const fb = cur.feedback
  // A sound move shows the position after it, with the Play board's star on the moved piece, and no arrows. The replay of
  // "what I played in the game" steps through its own positions, with no arrows.
  const replay = cur.stage === 'feedback' && !!fb && showGame ? replayStep(fb.game_line, step) : null
  const afterView = cur.stage === 'feedback' && !!fb && fb.sound && !showGame
  if (cur.stage === 'feedback' && fb) {
    if (replay) {
      for (const [sq, c] of Object.entries(replay.squares)) styles[sq] = { background: c }
    } else if (!afterView) {
      const m = feedbackMarks(fb, cur.fen, cur.side_to_move)
      for (const [sq, c] of Object.entries(m.squares)) styles[sq] = { background: c }
    }
    arrows = [] // the numbered overlay below replaces the library's plain arrows
  } else {
    const h = hintMarks(cur.hints)
    for (const [sq, c] of Object.entries(h.squares)) styles[sq] = { background: c }
    arrows = h.arrows
    if (cur.stage === 'recognition' && tap && tap !== NO_THREAT) styles[tap] = { background: 'rgba(255, 200, 0, 0.7)' }
    if (cur.stage === 'move') {
      if (from) styles[from] = { background: 'rgba(80, 140, 230, 0.45)' }
      for (const sq of targetsFrom(cur.legal_moves, from)) {
        const dot = pieceColorAt(cur.fen, sq)
          ? 'radial-gradient(circle, transparent 58%, rgba(0,0,0,0.25) 60%)'
          : 'radial-gradient(circle, rgba(0,0,0,0.25) 22%, transparent 24%)'
        styles[sq] = { ...styles[sq], backgroundImage: dot }
      }
      if (move) arrows = [...arrows, { startSquare: move.slice(0, 2), endSquare: move.slice(2, 4), color: 'rgba(80, 140, 230, 0.85)' }]
    }
  }
  const starSquare = afterView && fb ? fb.your_move.uci.slice(2, 4) : null
  // The board library skips its own square styling when a custom renderer returns something, so this applies `styles` itself.
  const squareRenderer = ({ square, children }: { square: string; children?: React.ReactNode }) => (
    <div style={{ position: 'relative', width: '100%', height: '100%', ...styles[square] }}>
      {children}
      {square === starSquare && <span className="move-badge best" title="Good move" aria-label="Good move">★</span>}
    </div>
  )
  const lanes = fb && !showGame ? feedbackLanes(fb, view.mistake_type) : []
  const lastOne = view.done + 1 === view.total
  const hintLabel = hintButton(cur.hint_level)

  return (
    <div className="app">
      <h2>{view.label}: position {cur.number} of {view.total}{cur.attempt > 1 ? ` · try ${cur.attempt}` : ''}</h2>
      <p className="status-line">
        You play {cur.side_to_move}, and it is your move. <span className="badge">assisted</span>
      </p>
      {view.repeat_games && cur.number === 1 && cur.attempt === 1 && (
        <p className="note small">Not enough different games left: some positions come from the same game.</p>
      )}
      <div className="board">
        <Chessboard options={{
          position: replay ? replay.fen : afterView && fb ? fb.fen_after : cur.fen,
          boardOrientation: cur.side_to_move,
          allowDragging: false,
          onSquareClick,
          squareStyles: styles,
          squareRenderer,
          arrows,
          id: 'practice-board',
        }} />
        {lanes.length > 0 && <MoveArrows lanes={lanes} orientation={cur.side_to_move} />}
      </div>
      {lanes.length > 0 && <LaneLegend lanes={lanes} />}
      {replay && fb && (
        <div className="replay">
          <span className="replay-caption">{replay.caption}</span>
        </div>
      )}

      {cur.stage !== 'feedback' && (
        <div className="feedback">
          <p><strong>{stepTitle(cur.stage, view.mistake_type)}</strong></p>
          {note && <p className="fb-wrong">{note}</p>}
          {cur.stage === 'recognition' ? (
            <>
              <div className="controls">
                <button className={tap === NO_THREAT ? 'on' : ''} onClick={() => { setNote(null); setTap(tap === NO_THREAT ? null : NO_THREAT) }}>
                  No immediate threat
                </button>
                <button disabled={!tap || busy} onClick={() => send('recognition', { ord: cur.ord, tap })}>
                  {busy ? 'Saving…' : 'Next: make your move'}
                </button>
              </div>
              {tap && <p>Your answer: {tapWords(tap)}.</p>}
            </>
          ) : (
            <>
              <p>Your answer to the question: {tapWords(cur.your_tap ?? NO_THREAT)}. {move ? `Your move: ${move.slice(0, 2)} to ${move.slice(2, 4)}.` : ''}</p>
              <div className="controls">
                <button disabled={!move || busy} onClick={() => send('move', { ord: cur.ord, move })}>
                  {busy ? 'Checking…' : 'Submit this move'}
                </button>
              </div>
            </>
          )}
          {cur.hints.map((h) => <p key={h.level} className="note"><strong>Hint {h.level}:</strong> {h.text}</p>)}
          {hintLabel && (
            <div className="controls">
              <button disabled={busy} onClick={() => send('hint', { ord: cur.ord }, true)}>{hintLabel}</button>
            </div>
          )}
          <p className="note small">Hints are for practice: this position is marked as assisted.</p>
        </div>
      )}

      {fb && (
        <div className={`feedback ${fb.sound ? 'good' : 'mistake'}`}>
          <p className={fb.tap_correct ? 'fb-right' : 'fb-wrong'}>
            You chose {tapWords(fb.your_tap)}: {fb.tap_correct ? 'right' : 'not right'}.
          </p>
          <div className="controls">
            <button className={showGame ? 'on' : ''} onClick={() => { setShowGame(!showGame); setStep(0) }}>
              {showGame ? 'Back to my move' : 'Replay what I played in the game'}
            </button>
            <button disabled={busy} onClick={() => send('retry', { ord: cur.ord })}>Try this position again</button>
            <button disabled={busy} onClick={() => send('next', { ord: cur.ord })}>{lastOne ? 'Finish' : 'Next position'}</button>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryPage({ summary, onHome }: { summary: PracticeSummary | null; onHome?: () => void }) {
  if (!summary) return <div className="app"><p>Loading…</p></div>
  return (
    <div className="spots">
      {onHome && <button onClick={onHome}>Back</button>}
      <h2>{summary.label}: practice summary</h2>
      <div className="card">
        {summaryLines(summary).map((l) => <p key={l} className="headline">{l}</p>)}
        <p className="note small">
          Practice is assisted, so this is not a test score. The delayed test (a few days later) shows whether it helped.
          {summary.repeat_games && ' Some positions came from the same game.'}
        </p>
        <p className="note"><strong>Next:</strong> {delayedSummaryLine(summary.delayed_test)}</p>
      </div>
      {summary.items.map((it) => {
        const squares: Record<string, React.CSSProperties> = {}
        const own = pieceColorAt(it.fen, it.target_squares[0] ?? '') === (it.side_to_move === 'white' ? 'w' : 'b')
        for (const sq of it.target_squares) squares[sq] = { background: own ? 'rgba(220, 60, 50, 0.6)' : 'rgba(60, 170, 90, 0.6)' }
        return (
          <div key={it.number} className={`feedback ${it.first_attempt_correct ? 'good' : 'slip'}`}>
            <p>
              <strong>Position {it.number}</strong>
              {it.first_attempt_correct && ' · right first try, no hint'}
              {it.assisted_correct && ' · right with a hint'}
              {it.needed_retry && ` · ${it.attempts} tries`}
              {it.seconds !== null && ` · ${it.seconds} s`}
            </p>
            <div className="moment-board">
              <Chessboard options={{ position: it.fen, boardOrientation: it.side_to_move, allowDragging: false, squareStyles: squares,
                id: `summary-${it.number}` }} />
            </div>
            <p>{it.original}</p>
          </div>
        )
      })}
    </div>
  )
}

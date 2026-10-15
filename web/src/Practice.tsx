import { useCallback, useEffect, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import { api } from './api'
import { NO_THREAT, castleMove, pickMove, pieceColorAt, tapRefusal, tapWords, targetsFrom } from './assessState'
import {
  feedbackMarks, hintButton, hintMarks, lineCaption, stepTitle, summaryLines,
  type PracticeSummary, type PracticeView,
} from './practiceState'

type Arrow = { startSquare: string; endSquare: string; color: string }

/** Replay My Mistakes (PRD v2 §6): positions from the player's own games, one at a time. Always assisted. */
export default function Practice({ id, onHome }: { id: number; onHome: () => void }) {
  const [view, setView] = useState<PracticeView | null>(null)
  const [summary, setSummary] = useState<PracticeSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tap, setTap] = useState<string | null>(null) // the answer to the question, before it is sent
  const [from, setFrom] = useState<string | null>(null)
  const [move, setMove] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null) // why a click did nothing (rules only, never a hint)

  // A new view from the server resets what the player had picked on the board, except after a hint (`keep`).
  const apply = useCallback((v: PracticeView, keep = false) => {
    setView(v)
    if (!keep) {
      setTap(null)
      setFrom(null)
      setMove(null)
      setNote(null)
    }
    if (v.status === 'completed') {
      api<PracticeSummary>(`/coach/practice/sessions/${v.session_id}/summary`).then(setSummary).catch((e: Error) => setError(e.message))
    }
  }, [])

  useEffect(() => {
    api<PracticeView>(`/coach/practice/sessions/${id}`).then((v) => apply(v)).catch((e: Error) => setError(e.message))
  }, [id, apply])

  function send(path: string, body: unknown, keep = false) {
    setBusy(true)
    api<PracticeView>(`/coach/practice/sessions/${id}/${path}`, body)
      .then((v) => apply(v, keep))
      .catch((e: Error) => setError(e.message))
      .finally(() => setBusy(false))
  }

  if (error) return <div className="app"><p className="error">{error}</p><button onClick={onHome}>Back</button></div>
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
  if (cur.stage === 'feedback' && cur.feedback) {
    const m = feedbackMarks(cur.feedback, cur.fen, cur.side_to_move)
    for (const [sq, c] of Object.entries(m.squares)) styles[sq] = { background: c }
    arrows = m.arrows
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
  const fb = cur.feedback
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
          position: cur.fen,
          boardOrientation: cur.side_to_move,
          allowDragging: false,
          onSquareClick,
          squareStyles: styles,
          arrows,
          id: 'practice-board',
        }} />
      </div>

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
          <p><strong>Your move {fb.your_move.san}: {fb.verdict}.</strong> {fb.avoids}</p>
          <p className={fb.tap_correct ? 'fb-right' : 'fb-wrong'}>
            You chose {tapWords(fb.your_tap)}: {fb.tap_correct ? 'right' : 'not right'}.
          </p>
          <p>{fb.original}</p>
          <p>{fb.allowed}</p>
          {!fb.sound && fb.good_moves.length > 0 && <p>Good moves here: {fb.good_moves.map((m) => m.san).join(', ')}.</p>}
          <p className="note small">{lineCaption(view.mistake_type)}</p>
          <div className="controls">
            <button disabled={busy} onClick={() => send('retry', { ord: cur.ord })}>Try this position again</button>
            <button disabled={busy} onClick={() => send('next', { ord: cur.ord })}>{lastOne ? 'Finish' : 'Next position'}</button>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryPage({ summary, onHome }: { summary: PracticeSummary | null; onHome: () => void }) {
  if (!summary) return <div className="app"><p>Loading…</p></div>
  return (
    <div className="spots">
      <button onClick={onHome}>Back</button>
      <h2>{summary.label}: practice summary</h2>
      <div className="card">
        {summaryLines(summary).map((l) => <p key={l} className="headline">{l}</p>)}
        <p className="note small">
          Practice is assisted, so this is not a test score. The delayed test (a few days later) shows whether it helped.
          {summary.repeat_games && ' Some positions came from the same game.'}
        </p>
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

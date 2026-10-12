import { useCallback, useEffect, useRef, useState } from 'react'
import { Chessboard } from 'react-chessboard'
import './App.css'
import { rapidLines, remainingMs, uciForClick, type RapidResult, type RapidSummary, type RapidView } from './trainState'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const LEAD_IN_MS = 700

type Phase = 'leadin' | 'play' | 'result'

export default function Rapid({ view, onExit }: { view: RapidView; onExit: () => void }) {
  const [index, setIndex] = useState(0)
  const [phase, setPhase] = useState<Phase>('leadin')
  const [left, setLeft] = useState(view.limit_s * 1000)
  const [selected, setSelected] = useState<string | null>(null)
  const [selectedPiece, setSelectedPiece] = useState<string | null>(null)
  const [result, setResult] = useState<RapidResult | null>(null)
  const [summary, setSummary] = useState<RapidSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const startedAt = useRef(0)
  const sending = useRef(false)
  const item = view.items[index]

  // Lead-in: show the position before their last move, then the position itself (the board animates their move).
  useEffect(() => {
    if (phase !== 'leadin') return
    const t = window.setTimeout(() => {
      startedAt.current = performance.now()
      setLeft(view.limit_s * 1000)
      setPhase('play')
    }, item.lead_in ? LEAD_IN_MS : 150)
    return () => window.clearTimeout(t)
  }, [phase, index, item.lead_in, view.limit_s])

  const submit = useCallback(
    async (uci: string | null) => {
      if (sending.current) return
      sending.current = true
      const elapsed = Math.round(performance.now() - startedAt.current)
      try {
        const res = await fetch(`${API}/training/rapid/${view.id}/items/${index}/attempt`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ uci, elapsed_ms: elapsed }),
        })
        const data = await res.json().catch(() => null)
        if (!res.ok) {
          setError((data as { message?: string } | null)?.message ?? `error ${res.status}`)
          sending.current = false // an illegal click is not a try: stay on the position
          return
        }
        setError(null)
        const r = data as RapidResult
        setResult(r)
        if (r.summary) setSummary(r.summary)
        setPhase('result')
      } catch {
        setError('Could not reach the server.')
      }
      sending.current = false
    },
    [index, view.id],
  )

  // The clock. Running out of time is a try (a real game does not wait).
  useEffect(() => {
    if (phase !== 'play') return
    const id = window.setInterval(() => {
      const remaining = remainingMs(view.limit_s, performance.now() - startedAt.current)
      setLeft(remaining)
      if (remaining <= 0) {
        window.clearInterval(id)
        void submit(null)
      }
    }, 100)
    return () => window.clearInterval(id)
  }, [phase, submit, view.limit_s])

  function next() {
    setResult(null)
    setSelected(null)
    setSelectedPiece(null)
    if (index + 1 >= view.items.length) {
      onExit()
      return
    }
    setIndex(index + 1)
    setPhase('leadin')
  }

  function onSquareClick({ piece, square }: { piece: { pieceType: string } | null; square: string }) {
    if (phase !== 'play') return
    const mine = piece !== null && piece.pieceType[0] === (item.side === 'white' ? 'w' : 'b')
    if (mine) {
      setSelectedPiece(square === selected ? null : piece.pieceType)
      return setSelected(square === selected ? null : square)
    }
    if (!selected) return
    const uci = uciForClick(selected, square, selectedPiece)
    setSelected(null)
    setSelectedPiece(null)
    void submit(uci)
  }

  const showFen = phase === 'leadin' && item.lead_in ? item.lead_in.fen : item.fen
  const styles: Record<string, React.CSSProperties> = {}
  if (selected) styles[selected] = { background: 'rgba(255, 200, 0, 0.45)' }
  if (phase === 'result' && result?.answer) {
    styles[result.answer.uci.slice(0, 2)] = { background: 'rgba(60, 170, 90, 0.35)' }
    styles[result.answer.uci.slice(2, 4)] = { background: 'rgba(60, 170, 90, 0.55)' }
  }
  const pct = Math.round((left / (view.limit_s * 1000)) * 100)
  const lastOne = index + 1 >= view.items.length

  return (
    <main className="train layout">
      <div className="board-col">
        <div className="board">
          <Chessboard
            options={{ position: showFen, boardOrientation: item.side, allowDragging: false, onSquareClick, squareStyles: styles, id: 'rapid-board' }}
          />
        </div>
      </div>
      <aside className="side-col">
        <p className="status-line">
          <strong>Rapid drill {index + 1} of {view.items.length}</strong> · you play {item.side}
        </p>
        <div aria-label="Time left" style={{ height: 10, background: 'var(--border)', borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ width: `${phase === 'result' ? 0 : pct}%`, height: '100%', background: pct > 30 ? 'rgb(60,170,90)' : 'rgb(200,70,60)' }} />
        </div>
        <p className="hint-count">{phase === 'play' ? `${(left / 1000).toFixed(1)} s` : phase === 'leadin' ? 'Watch their move…' : ' '}</p>
        {view.scan_prompt && phase === 'play' && <p className="hint-card">{view.scan_prompt}</p>}
        {phase === 'play' && <p>One try, like a real game. Click a piece, then where it goes.</p>}

        {phase === 'result' && result && (
          <section className="hint-card" role="status">
            <h3>
              {result.timed_out ? 'Out of time' : result.correct ? 'Good' : 'Not this one'}
              {result.answer ? `: ${result.answer.san}` : ''}
            </h3>
            <p className="hint-count">This was: {result.kind_label}.</p>
            {result.answer && <p>{result.answer.why}</p>}
            {result.facts.length > 0 && <ul>{result.facts.map((f) => <li key={f}>{f}</li>)}</ul>}
            <button className="primary" onClick={next}>{lastOne ? 'Finish' : 'Next position'}</button>
          </section>
        )}
        {error && <p role="alert">{error}</p>}
        {summary && lastOne && phase === 'result' && (
          <section className="hint-card">
            <h3>Drill done</h3>
            <ul>{rapidLines(summary).map((l) => <li key={l}>{l}</li>)}</ul>
          </section>
        )}
      </aside>
    </main>
  )
}

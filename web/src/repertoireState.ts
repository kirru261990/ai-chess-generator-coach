export interface OpeningRow {
  key: string
  name: string
  side: 'white' | 'black'
  available: boolean
  lines?: number
  nodes_ours?: number
  nodes_seen?: number
  nodes_engine?: number
  hits?: number
  misses?: number
  games?: number
  stopped?: number
  unchecked?: boolean
}

export interface Question {
  run_id: number
  key: string
  name: string
  side: 'white' | 'black'
  fen: string
  ply: number
  history: string[]
  legal: string[]
  assisted: true
  source: 'players' | 'engine'
  learn: boolean
  arrow: string | null
}

export interface Answer {
  matched: boolean
  retry: boolean
  attempts: number
  learn: boolean
  expected_san: string | null
  expected_uci: string | null
  your_san: string
  your_uci: string
  assisted: true
  after_fen?: string
  reply_san?: string[]
  reply_fen?: string
  next: Question | null
  summary?: { answered: number; hits: number; misses: number; shown: number }
}

export interface OpeningCard {
  title: string
  side: string
  progress: string | null
  engineNote: string | null
  accuracy: string | null
  note: string | null
  canStart: boolean
}

export function openingCard(o: OpeningRow): OpeningCard {
  const side = o.side === 'white' ? 'You play White' : 'You play Black'
  if (!o.available) {
    return { title: o.name, side, progress: null, engineNote: null, accuracy: null, note: 'No book built yet. Run the line builder first.', canStart: false }
  }
  const answered = (o.hits ?? 0) + (o.misses ?? 0)
  const notes = [
    o.unchecked ? 'Moves are not engine-checked yet.' : null,
    (o.stopped ?? 0) > 0
      ? `${o.stopped} ${o.stopped === 1 ? 'line ends' : 'lines end'} early where no common move passed the engine check.`
      : null,
  ].filter((n): n is string => n !== null)
  return {
    title: o.name,
    side,
    progress: `${o.nodes_seen ?? 0} of ${o.nodes_ours ?? 0} positions practised`,
    engineNote:
      (o.nodes_engine ?? 0) > 0 ? `${o.nodes_engine} of those positions are the engine's choice where players' games run out.` : null,
    accuracy: answered > 0 ? `${o.hits ?? 0} of ${answered} answers right` : null,
    note: notes.length ? notes.join(' ') : null,
    canStart: true,
  }
}

export function historyText(history: string[]): string {
  if (history.length === 0) return 'No moves yet. You play the first move.'
  return history.map((m, i) => (i % 2 === 0 ? `${i / 2 + 1}. ${m}` : m)).join(' ')
}

/** The last few moves, on one line, so the line does not grow and push the board down as the game goes on. */
export function recentText(history: string[], plies = 6): string {
  if (history.length === 0) return 'No moves yet. You play the first move.'
  const start = Math.max(0, history.length - plies)
  const moves = history.slice(start).map((m, i) => {
    const n = start + i
    if (n % 2 === 0) return `${n / 2 + 1}. ${m}`
    return i === 0 ? `${(n - 1) / 2 + 1}... ${m}` : m // a line that starts on Black's move says so
  })
  return (start > 0 ? '… ' : '') + moves.join(' ')
}

export function answerBanner(a: Pick<Answer, 'matched' | 'expected_san'>): { tone: 'right' | 'wrong'; text: string } {
  if (a.matched) return { tone: 'right', text: `Right: ${a.expected_san}.` }
  return a.expected_san
    ? { tone: 'wrong', text: `Not the line's move. The line plays ${a.expected_san}: follow the arrow.` }
    : { tone: 'wrong', text: "Not the line's move. Try again." }
}

export function summaryText(s: { answered: number; hits: number; misses: number; shown: number }): string {
  if (s.shown > 0 && s.hits + s.misses === 0) return `You played all ${s.shown} moves with the arrow.`
  const base = `${s.hits} of ${s.answered} right first time.`
  return s.misses > 0 ? `${base} ${s.misses} will come back sooner.` : base
}

export function arrowFor(q: Question | null, a: Answer | null): { startSquare: string; endSquare: string; color: string }[] {
  const uci = q?.arrow ?? (a && a.retry ? a.expected_uci : null)
  return uci ? [{ startSquare: uci.slice(0, 2), endSquare: uci.slice(2, 4), color: 'rgba(80, 140, 230, 0.85)' }] : []
}

export function sourceLabel(source: Question['source']): string | null {
  return source === 'engine' ? "Engine line: the engine's choice here, not what most players at this level play." : null
}

/** How long the player's own move stays alone on the board before the opponent's reply is drawn (a beat, as in Practice). */
export const REPLY_DELAY_MS = 500
/** How long the last position of a finished line stays up before the summary replaces it. */
export const END_HOLD_MS = 900

export type Stage = { fen: string; afterMs: number; then: 'next' | 'finish' | null }

/** What to draw after a right move: the player's move now, then the reply a beat later, then the next question or the summary. */
export function stagesFor(a: Pick<Answer, 'after_fen' | 'reply_fen' | 'reply_san' | 'next'>): Stage[] {
  if (!a.after_fen) return []
  const replied = (a.reply_san?.length ?? 0) > 0 && a.reply_fen
  const out: Stage[] = [{ fen: a.after_fen, afterMs: 0, then: null }]
  if (replied) out.push({ fen: a.reply_fen as string, afterMs: REPLY_DELAY_MS, then: a.next ? 'next' : null })
  if (!a.next) out.push({ fen: (replied ? a.reply_fen : a.after_fen) as string, afterMs: END_HOLD_MS, then: 'finish' })
  else if (!replied) out.push({ fen: a.after_fen, afterMs: REPLY_DELAY_MS, then: 'next' })
  return out
}

export type Current = { finished: false; question: Question } | { finished: true; fen: string; summary: NonNullable<Answer['summary']> }

/** True when the screen cannot tell whether the server took the answer (the response was lost, or the question was already answered),
 *  so it should ask the server where the run is instead of guessing. */
export function needsResync(e: { code?: string; status?: number }): boolean {
  return e.code === 'stale_question' || e.status === undefined
}

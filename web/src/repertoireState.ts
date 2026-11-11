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

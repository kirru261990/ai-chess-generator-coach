export interface OpeningRow {
  key: string
  name: string
  side: 'white' | 'black'
  available: boolean
  lines?: number
  nodes_ours?: number
  nodes_seen?: number
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
}

export interface Answer {
  matched: boolean
  expected_san: string
  expected_uci: string
  your_san: string
  your_uci: string
  assisted: true
  next: Question | null
  summary?: { answered: number; hits: number; misses: number }
}

export interface OpeningCard {
  title: string
  side: string
  progress: string | null
  accuracy: string | null
  note: string | null
  canStart: boolean
}

export function openingCard(o: OpeningRow): OpeningCard {
  const side = o.side === 'white' ? 'You play White' : 'You play Black'
  if (!o.available) {
    return { title: o.name, side, progress: null, accuracy: null, note: 'No book built yet. Run the line builder first.', canStart: false }
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
    accuracy: answered > 0 ? `${o.hits ?? 0} of ${answered} answers right` : null,
    note: notes.length ? notes.join(' ') : null,
    canStart: true,
  }
}

export function historyText(history: string[]): string {
  if (history.length === 0) return 'No moves yet. You play the first move.'
  return history.map((m, i) => (i % 2 === 0 ? `${i / 2 + 1}. ${m}` : m)).join(' ')
}

export function answerBanner(a: Pick<Answer, 'matched' | 'expected_san' | 'your_san'>): { tone: 'right' | 'wrong'; text: string } {
  return a.matched
    ? { tone: 'right', text: `Right: ${a.expected_san}.` }
    : { tone: 'wrong', text: `You played ${a.your_san}. The line plays ${a.expected_san}. It will come back sooner.` }
}

export function summaryText(s: { answered: number; hits: number; misses: number }): string {
  const base = `${s.hits} of ${s.answered} right.`
  return s.misses > 0 ? `${base} ${s.misses} will come back sooner.` : base
}

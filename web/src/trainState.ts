// Pure helpers for the Train tab: no network, no React.

export type Motif = 'hanging_own' | 'missed_free'
export type ItemKind = 'own' | 'practice' | 'retest' | 'held_out'
export type SessionItem = { index: number; kind: ItemKind; fen: string; side: 'white' | 'black'; hints_allowed: boolean; done: boolean }
export type Session = { id: string; motif: Motif; motif_label: string; items: SessionItem[] }
export type Answer = { uci: string; san: string; why: string; played_san?: string }
export type AttemptResult = {
  index: number
  correct: boolean
  accepted_by: string | null
  first_try: boolean
  assisted: boolean
  finished: boolean
  facts: string[]
  answer?: Answer
}
export type ItemOutcome = { index: number; kind: ItemKind; correct: boolean; firstTry: boolean; assisted: boolean; gaveUp: boolean }

export const KIND_LABEL: Record<ItemKind, string> = {
  own: 'From your games',
  practice: 'Practice puzzle',
  retest: 'Retest: you missed this a week ago',
  held_out: 'Test: no hints, one try',
}

/** The UCI for a click on `square` after `from` was selected. A pawn reaching the last rank queens. */
export function uciForClick(from: string, to: string, pieceType: string | null): string {
  const lastRank = to.endsWith('8') || to.endsWith('1')
  const pawn = pieceType !== null && pieceType[1]?.toLowerCase() === 'p'
  return `${from}${to}${pawn && lastRank ? 'q' : ''}`
}

/** The summary shown at the end of a session. Counts first, never a bare rate (rule 3). */
export function summarise(outcomes: ItemOutcome[]) {
  const practice = outcomes.filter((o) => o.kind !== 'held_out')
  const held = outcomes.find((o) => o.kind === 'held_out') ?? null
  return {
    practiceTotal: practice.length,
    firstTryCorrect: practice.filter((o) => o.firstTry && o.correct).length,
    firstTryCleanCorrect: practice.filter((o) => o.firstTry && o.correct && !o.assisted).length,
    gaveUp: practice.filter((o) => o.gaveUp).length,
    heldOut: held ? (held.correct ? 'passed' : 'missed') : 'not tried',
  }
}

export function summaryLines(s: ReturnType<typeof summarise>): string[] {
  const lines = [
    `${s.firstTryCorrect} of ${s.practiceTotal} practice positions right on the first try` +
      (s.firstTryCorrect > 0 ? ` (${s.firstTryCleanCorrect} with no hints)` : ''),
  ]
  if (s.gaveUp > 0) lines.push(`${s.gaveUp} shown the answer`)
  lines.push(`Test position: ${s.heldOut}`)
  return lines
}

// ---------------------------------------------------------------- rapid drill

export type RapidKind = 'hang' | 'free' | 'calm' | 'test'
export type RapidItem = { index: number; fen: string; side: 'white' | 'black'; lead_in?: { fen: string; uci: string } }
export type RapidView = { id: string; limit_s: number; prompted: boolean; scan_prompt: string | null; items: RapidItem[] }
export type RapidKindStats = { attempts: number; correct: number; timed_out: number; careless: number; median_seconds: number | null }
export type RapidSummary = { attempts: number; by_kind: Record<RapidKind, RapidKindStats> }
export type RapidResult = {
  index: number
  correct: boolean
  timed_out: boolean
  careless: boolean
  kind: RapidKind
  kind_label: string
  answer: Answer | null
  facts: string[]
  summary?: RapidSummary
}

export const RAPID_KIND_NAME: Record<RapidKind, string> = {
  hang: 'A piece of yours could be taken',
  free: 'A free piece to take',
  calm: 'Nothing needed doing',
  test: 'Test positions',
}

export function remainingMs(limitS: number, elapsedMs: number): number {
  return Math.max(0, limitS * 1000 - elapsedMs)
}

/** One line per kind of position, as counts with their denominators. Kinds not met are left out. */
export function rapidLines(s: RapidSummary): string[] {
  const order: RapidKind[] = ['hang', 'free', 'calm', 'test']
  return order
    .filter((k) => s.by_kind[k].attempts > 0)
    .map((k) => {
      const x = s.by_kind[k]
      const parts = [`${x.correct} of ${x.attempts} right`]
      if (x.timed_out > 0) parts.push(`${x.timed_out} out of time`)
      if (x.median_seconds !== null) parts.push(`median ${x.median_seconds.toFixed(1)} s`)
      return `${RAPID_KIND_NAME[k]}: ${parts.join(', ')}`
    })
}

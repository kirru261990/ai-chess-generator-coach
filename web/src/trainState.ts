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

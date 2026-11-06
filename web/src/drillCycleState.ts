/** Words and numbers for Drill cycles (ADR 0018). Pure, so it is tested without a screen. */

export type CycleRow = {
  number: number
  finished: boolean
  answered: number
  total: number
  matched: number
  total_ms: number
  median_ms: number | null
  chance: number | null
  vs_previous?: { total_ms: number; matched: number; same_size: boolean }
}

export type Overview = { has_set: boolean; set_id?: number; size?: number; cycles: CycleRow[] }

export type Question = {
  done: false
  cycle: number
  position: number
  total: number
  drill_id: string
  fen: string
  side: 'white' | 'black'
  question: string
  legal_moves: string[]
}

export type Feedback = {
  matched: boolean
  your_move: string
  checked_moves: string[]
  checked_uci: string[]
  elapsed_ms: number
  in_the_game: string
  note: string
  not_checked?: string
}

export type Current = Question | { done: true; cycle: number; summary: Overview }

export function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  const rest = s % 60
  return rest === 0 ? `${m} min` : `${m} min ${rest} s`
}

/** "31 of 50 matched (a random legal move would match about 4%)": a rate always has its denominator and its guess level. */
export function matchLine(c: CycleRow): string {
  const guess = c.chance === null ? '' : ` (a random legal move would match about ${Math.round(c.chance * 100)}%)`
  return `${c.matched} of ${c.answered} matched${guess}`
}

/** How a finished cycle compares with the one before, or null when the two are not the same size. */
export function compareLine(c: CycleRow): string | null {
  const v = c.vs_previous
  if (!c.finished || !v || !v.same_size) return null
  const t = Math.abs(v.total_ms)
  const time = t < 1000 ? 'the same time' : `${formatDuration(t)} ${v.total_ms < 0 ? 'faster' : 'slower'}`
  const m = v.matched === 0 ? 'the same number matched' : `${Math.abs(v.matched)} ${v.matched > 0 ? 'more' : 'fewer'} matched`
  return `${time} than cycle ${c.number - 1}, ${m}`
}

/** The goal line for the next cycle. Speed only counts when matching holds: both are shown, neither is a target to chase alone. */
export function nextGoal(rows: CycleRow[]): string | null {
  const last = rows.filter((r) => r.finished).at(-1)
  if (!last) return null
  return `Next cycle: beat ${formatDuration(last.total_ms)} and keep at least ${last.matched} of ${last.answered} matched. Slow down if you start guessing.`
}

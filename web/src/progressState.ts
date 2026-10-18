/**
 * Pure helpers for the delayed test and the Progress screen (PRD v2 §7.2, §7.6, §13). The server owns every number; these only
 * shape words. Unassisted tests and assisted practice are always kept apart.
 */
import { scoreLine } from './assessState'

export type DelayedHome = {
  waiting: { assessment_id: number; status: string; due_at: string; available: boolean } | null
  done: number[]
}

export type DelayedTestInfo =
  | { status: 'scheduled'; assessment_id: number; due_at: string }
  | { status: 'pending_exists'; assessment_id?: number; due_at?: string } // the ids only while that test still waits
  | { status: 'no_positions' }
  | { status: 'error' }
  | { status: 'not_set' } // a session finished before delayed tests existed

export type TestSummary = {
  assessment_id: number
  kind: 'BASELINE' | 'DELAYED'
  question_version: string
  total: number
  left_out_count: number
  scores: { recognition: number; move: number; combined: number }
  chance: { recognition: number; move: number | null; combined: number | null }
  chance_pending: boolean
  mean_seconds: number | null
  timed: number
  interrupted: number
}

export type Comparison = {
  baseline: { move: number; total: number }
  delayed: { assessment_id: number; total: number; move: number | null; recognition: number | null; combined: number | null }[]
  comparable: { move: boolean; recognition: boolean }
  gain_move_positions_of_5?: number
  gain_combined_positions_of_5?: number
}

export type PracticeStats = {
  assisted: true
  sessions: number
  positions: number
  first_attempts: number
  first_attempt_correct: number
  assisted_correct: number
  recognized: number
  attempts: number
  retries: number
  attempts_with_hint: number
  mean_first_seconds: number | null
  not_sound: number
  reasons: { reason: string; count: number }[]
}

export type ProgressType = {
  mistake_type: 'M1' | 'M2'
  label: string
  baseline: TestSummary | null
  delayed: TestSummary[]
  set_aside: number
  waiting: { assessment_id: number; due_at: string; available: boolean } | null
  comparison: Comparison | null
  practice: PracticeStats
}

export type Progress = { types: ProgressType[]; targets_delayed_per_type: number }

const HOUR_MS = 3_600_000

/** When a delayed test opens, in words: "Open now", or the local date and time with the hours left. */
export function dueText(dueIso: string, now: number = Date.now()): string {
  const due = Date.parse(dueIso)
  if (Number.isNaN(due) || due <= now) return 'Open now'
  const hours = Math.ceil((due - now) / HOUR_MS)
  const when = new Date(due).toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  return `Opens ${when} (in about ${hours} hour${hours === 1 ? '' : 's'})`
}

/** What a home card says about the delayed test, and the test to open when it can be taken. */
export function delayedLabel(d: DelayedHome, now: number = Date.now()): { note: string | null; takeId: number | null } {
  const done = d.done.length
  const doneNote = done > 0 ? `Delayed tests done: ${done}.` : null
  if (!d.waiting) return { note: doneNote, takeId: null }
  if (d.waiting.available) {
    return { note: `Your delayed test is open. ${doneNote ?? ''}`.trim(), takeId: d.waiting.assessment_id }
  }
  return { note: `Your delayed test. ${dueText(d.waiting.due_at, now)}. ${doneNote ?? ''}`.trim(), takeId: null }
}

/** The line on the practice summary about the delayed test. */
export function delayedSummaryLine(t: DelayedTestInfo, now: number = Date.now()): string {
  if (t.status === 'scheduled') return `Your delayed test is set. ${dueText(t.due_at, now)}. It uses positions you have not seen, with no help.`
  if (t.status === 'pending_exists') {
    const when = t.due_at ? ` ${dueText(t.due_at, now)}.` : ''
    return `Another test was already waiting when you finished, so none was set for this session.${when} Take it, and the next session will set the next one.`
  }
  if (t.status === 'no_positions') return 'No unused positions were left to set a delayed test for this mistake type.'
  if (t.status === 'error') return 'Something went wrong setting your delayed test, so none was set. Your practice was saved.'
  return 'No delayed test was set for this session.'
}

function pct(x: number | null): string {
  return x === null ? 'n/a' : `${Math.round(x * 100)}%`
}

/** One test as a line: the move score first (always comparable), then the other two, each with its guessing level. */
export function testLines(t: TestSummary): string[] {
  const lines = [
    `Played a sound move: ${scoreLine(t.scores.move, t.total, t.chance.move)}`,
    `Spotted the problem: ${scoreLine(t.scores.recognition, t.total, t.chance.recognition)}`,
    `Both right: ${scoreLine(t.scores.combined, t.total, t.chance.combined)}`,
  ]
  if (t.left_out_count > 0) lines.push(`${t.left_out_count} position(s) left out of the score (unfair question).`)
  if (t.mean_seconds !== null) lines.push(`Average time per position: ${t.mean_seconds} s (${t.timed} timed).`)
  if (t.question_version === '1') lines.push('First wording of the tap question: its tap score is not comparable with later tests.')
  return lines
}

/** The starting test against the delayed tests, in positions out of 5 (PRD §13). Directional, never proof. */
export function comparisonLines(c: Comparison): string[] {
  const lines = [`Sound move: starting test ${pct(c.baseline.move)}; ` + c.delayed.map((d, i) => `delayed test ${i + 1} ${pct(d.move)}`).join('; ') + '.']
  if (c.gain_move_positions_of_5 !== undefined) {
    const g = c.gain_move_positions_of_5
    lines.push(`Change in sound moves, averaged over the delayed tests: ${g > 0 ? '+' : ''}${g} positions out of 5.`)
  }
  if (!c.comparable.recognition) lines.push('Spotting and "both right" are not compared: the starting test used the first wording of the question.')
  else if (c.gain_combined_positions_of_5 !== undefined) {
    const g = c.gain_combined_positions_of_5
    lines.push(`Change in "both right": ${g > 0 ? '+' : ''}${g} positions out of 5.`)
  }
  lines.push('Five positions is a small sample: treat this as direction, not proof.')
  return lines
}

/** Assisted practice for one type. */
export function practiceLines(p: PracticeStats): string[] {
  if (p.sessions === 0 && p.attempts === 0) return ['No practice yet.']
  const lines = [
    `Sessions finished: ${p.sessions}. Positions tried: ${p.positions}.`,
    `First try, right with no hint: ${p.first_attempt_correct} of ${p.first_attempts}. Right with a hint: ${p.assisted_correct} of ${p.first_attempts}.`,
    `Spotted the problem yourself on the first try: ${p.recognized} of ${p.first_attempts}.`,
    `Hints used on ${p.attempts_with_hint} of ${p.attempts} tries. Extra tries: ${p.retries}.`,
  ]
  if (p.mean_first_seconds !== null) lines.push(`Average time on a first try: ${p.mean_first_seconds} s.`)
  if (p.reasons.length > 0) lines.push('Why moves were not sound: ' + p.reasons.map((r) => `${r.reason} (${r.count})`).join('; ') + '.')
  return lines
}

/** Real-game rates (PRD v2 §8, Step 4b). The server owns every number; these only shape words. */
export type RealWindow = {
  games_in_window: number
  games: number
  missing_games: number
  player_moves: number
  denominator: number
  events: number
  uncertain: number
  skipped: number
  rate: number | null // M1: per 100 player moves; M2: a share from 0 to 1
  interval: [number, number] | null
}

export type RealComparison = {
  state: 'ok' | 'not_enough_data' | 'analysis_incomplete'
  floor: number
  floor_unit: 'games' | 'opportunities'
  reason?: 'no_countable_moves' | 'below_floor'
  baseline_has: number
  post_has: number
  change?: number
  direction?: 'lower' | 'higher' | 'same'
  ranges_overlap?: boolean
}

export type RealTimeControl = { time_control: string; label: string; baseline: RealWindow; post: RealWindow; comparison: RealComparison }

export type RealType = {
  mistake_type: 'M1' | 'M2'
  label: string
  detector: string
  status: 'started' | 'not_started'
  frozen_at: string | null
  engine_config_id?: string | null
  time_controls: RealTimeControl[]
}

export type RealGame = {
  rates_version: string
  label: string
  floors: { games: number; opportunities: number }
  engine_config_ids: string[]
  types: RealType[]
}

function rateWords(w: RealWindow, mtype: 'M1' | 'M2'): string {
  if (w.rate === null || w.interval === null) return 'no rate yet'
  const one = (x: number) => (mtype === 'M1' ? `${x.toFixed(1)}` : `${Math.round(x * 100)}%`)
  const range = `${one(w.interval[0])} to ${one(w.interval[1])}`
  return mtype === 'M1' ? `${one(w.rate)} per 100 moves (range ${range})` : `${one(w.rate)} missed (range ${range})`
}

/** One window as lines: the rate, then every denominator, then what was left out (abstentions are in neither number). */
export function realWindowLines(w: RealWindow, mtype: 'M1' | 'M2'): string[] {
  const what = mtype === 'M1' ? `${w.events} mistakes in ${w.denominator} player moves` : `${w.events} missed of ${w.denominator} free captures available`
  const lines = [`${rateWords(w, mtype)}`, `${what}; ${w.games} game${w.games === 1 ? '' : 's'}.`]
  if (w.uncertain > 0) lines.push(`${w.uncertain} move(s) left out because the check was not certain.`)
  if (w.missing_games > 0) lines.push(`${w.missing_games} game(s) not checked yet.`)
  return lines
}

/** What the before/after comparison says: only above the floors, never as proof. */
export function realComparisonLine(c: RealComparison, mtype: 'M1' | 'M2'): string {
  if (c.state === 'analysis_incomplete') return 'Some games are not checked yet, so there is no comparison.'
  if (c.state === 'not_enough_data') {
    if (c.reason === 'no_countable_moves') {
      return `Not enough data yet: a window has no countable moves (before ${c.baseline_has} ${c.floor_unit}, after ${c.post_has}).`
    }
    return `Not enough data yet: a comparison needs at least ${c.floor} ${c.floor_unit} in each window (before ${c.baseline_has}, after ${c.post_has}).`
  }
  const amount = mtype === 'M1' ? `${Math.abs(c.change ?? 0).toFixed(1)} per 100 moves` : `${Math.round(Math.abs(c.change ?? 0) * 100)} points`
  const move = c.direction === 'same' ? 'no change' : `${amount} ${c.direction}`
  return `After against before: ${move}. ` + (c.ranges_overlap
    ? 'The ranges overlap, so this could be chance.' : 'The ranges do not overlap, so this is less likely to be chance. Still directional, not proof of cause.')
}

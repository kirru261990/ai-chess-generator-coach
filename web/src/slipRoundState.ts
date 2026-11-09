/** Words, numbers and board marks for Slip rounds (ADR 0020, 0021). Pure, so it is tested without a screen. */
import { formatDuration } from './drillCycleState'

export type Step = { uci: string; san: string; who: 'you' | 'they'; points: number; fen: string }
export type Review = { start_fen: string; mine: Step[]; better: Step[] }
export type Line = 'mine' | 'better'

export type Question = {
  done: false
  round: number
  position: number
  total: number
  drill_id: string
  fen: string
  side: 'white' | 'black'
  question: string
  legal_moves: string[]
  timer_s: number
}

export type WhyMark = { step: number; text: string; arrows: { from: string; to: string; tone: 'their' | 'better' }[]; squares: string[] }
export type Why = { mine: WhyMark | null; better: WhyMark | null }
export type Cause = { cause: string; sentence: string; habit: string | null; why: Why | null }

export type Answer = {
  matched: boolean
  your_move: string
  your_uci: string
  checked_moves: string[]
  checked_uci: string[]
  in_the_game: string
  note: string
  not_checked?: string
  elapsed_ms: number
  timer_s: number
  over_time: boolean
  cause: Cause
  review: Review | null
}

export type RoundSummary = { answered: number; total: number; matched: number; over_time: number; median_ms: number | null }
export type Current = Question | { done: true; round: number; summary: RoundSummary }

export const TIMER_CHOICES = [
  { seconds: 15, label: '15 seconds', hint: 'your average in a 10-minute game' },
  { seconds: 8, label: '8 seconds', hint: 'pressure' },
  { seconds: 0, label: 'No timer', hint: 'learning' },
]

const LOW_MS = 3_000

/** The countdown for one position: how full the bar is, the words beside it, and whether it is low or over. */
export function timerState(timerS: number, elapsedMs: number) {
  if (timerS === 0) return { fraction: 1, label: 'No timer', level: 'none' as const }
  const left = timerS * 1000 - elapsedMs
  if (left <= 0) return { fraction: 0, label: 'Over time', level: 'over' as const }
  return { fraction: left / (timerS * 1000), label: `${Math.ceil(left / 1000)} s`, level: left <= LOW_MS ? ('low' as const) : ('ok' as const) }
}

export function pointsTag(points: number): string {
  if (points === 0) return 'Level'
  const n = Math.abs(points)
  return `You ${points > 0 ? '+' : '−'}${n} ${n === 1 ? 'point' : 'points'}`
}

const RED = [217, 83, 79]
const GREEN = [60, 154, 95]
const ORANGE = [240, 173, 78]
const rgba = (c: number[], a: number) => `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${a})`

export type Frame = {
  fen: string
  arrows: { startSquare: string; endSquare: string; color: string }[]
  caption: string
  points: string | null
  step: number
  last: number
}

/** The board after `step` moves of a line: the latest move a bold arrow, earlier moves faded. Red is your move, green the better move, orange theirs. */
export function reviewFrame(review: Review, line: Line, step: number): Frame {
  const steps = review[line]
  const last = steps.length
  if (step <= 0) return { fen: review.start_fen, arrows: [], caption: 'Start', points: null, step: 0, last }
  const upto = steps.slice(0, step)
  const mine = line === 'mine' ? RED : GREEN
  const arrows = upto.map((s, i) => ({
    startSquare: s.uci.slice(0, 2),
    endSquare: s.uci.slice(2, 4),
    color: rgba(s.who === 'you' ? mine : ORANGE, i === upto.length - 1 ? 0.8 : 0.3),
  }))
  const cur = upto[upto.length - 1]
  return { fen: cur.fen, arrows, caption: `${cur.who === 'you' ? 'You' : 'They'}: ${cur.san}`, points: pointsTag(cur.points), step, last }
}

export function clampStep(review: Review, line: Line, step: number): number {
  return Math.max(0, Math.min(review[line].length, step))
}

/** One short line: the move, whether it matched the engine-checked moves (never "wrong"), the time, and over time. */
export function answerLine(a: Pick<Answer, 'matched' | 'your_move' | 'elapsed_ms' | 'over_time'>): string {
  return `${a.your_move} ${a.matched ? 'matched' : 'not matched'} · ${formatDuration(a.elapsed_ms)}${a.over_time ? ' · over time' : ''}`
}

export type Badge = { square: string; symbol: string; tone: string; label: string }
const BLUE = 'rgba(80, 140, 230, 0.85)'
const TONE = { their: 'rgba(240, 173, 78, 0.8)', better: 'rgba(60, 154, 95, 0.8)' }

/** What to draw on the board for this frame, in the same style as the Practice board: a blue arrow for your answer (with a star when it
 *  matched), a badge on the moved piece for the first move of each line, and, at the step it belongs to, the why: one sentence, the arrows
 *  it talks about and a ring on the square. A miss gets no badge: the engine did not rule on it. */
export function boardMarks(frame: Frame, line: Line, answered: { uci: string; matched: boolean }, why?: Why | null) {
  let arrows = frame.arrows
  let badge: Badge | null = null
  if (frame.step === 0) {
    arrows = [{ startSquare: answered.uci.slice(0, 2), endSquare: answered.uci.slice(2, 4), color: BLUE }]
    if (answered.matched) badge = { square: answered.uci.slice(2, 4), symbol: '★', tone: 'best', label: 'Matches the checked moves' }
  } else if (frame.step === 1) {
    const last = frame.arrows[0]
    badge = line === 'mine'
      ? { square: last.endSquare, symbol: '?', tone: 'mistake', label: 'The move you played in the game' }
      : { square: last.endSquare, symbol: '★', tone: 'best', label: 'The better move' }
  }
  const mark = why?.[line]
  if (!mark || mark.step !== frame.step) return { arrows, badge, squares: [] as string[], text: null as string | null }
  const extra = mark.arrows.map((a) => ({ startSquare: a.from, endSquare: a.to, color: TONE[a.tone] }))
  return { arrows: [...arrows, ...extra], badge, squares: mark.squares, text: mark.text as string | null }
}

/** "6 of 10 matched · 2 of 10 over time · middle time 9 s": every count keeps its denominator. */
export function roundLine(s: RoundSummary): string {
  const time = s.median_ms === null ? '' : ` · middle time ${formatDuration(s.median_ms)}`
  return `${s.matched} of ${s.answered} matched · ${s.over_time} of ${s.answered} over time${time}`
}

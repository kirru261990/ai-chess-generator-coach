/**
 * Pure helpers for Replay My Mistakes (PRD v2 §6). The server owns every answer, verdict and hint; these only shape what the
 * player sees. Before the first answer the server sends the board, the side to move, the legal moves and the pieces that can
 * be tapped, and nothing else.
 */
import { pieceColorAt, type MoveRef } from './assessState'
import type { DelayedTestInfo } from './progressState'

export type Hint = {
  level: number
  kind: 'last_move' | 'piece' | 'line'
  text: string
  squares?: string[]
  uci?: string[]
  san?: string[]
}

export type PracticeFeedback = {
  original: string
  game_move: MoveRef
  allowed: string
  board_line: string[] // M1: your move in the game, then what it allowed. M2: the capture
  target_squares: string[]
  your_tap: string
  tap_correct: boolean
  your_move: MoveRef
  sound: boolean
  verdict: 'SOUND' | 'NOT SOUND'
  avoids: string
  good_moves: MoveRef[]
  hint_level: number
}

export type PracticeCurrent = {
  ord: number
  number: number
  fen: string
  side_to_move: 'white' | 'black'
  legal_moves: string[]
  tap_squares: string[]
  attempt: number
  stage: 'recognition' | 'move' | 'feedback'
  your_tap: string | null
  hint_level: number
  hints: Hint[]
  feedback: PracticeFeedback | null
}

export type PracticeView = {
  session_id: number
  mistake_type: 'M1' | 'M2'
  label: string
  status: string
  total: number
  done: number
  repeat_games: boolean
  current: PracticeCurrent | null
}

export type SummaryItem = {
  number: number
  fen: string
  side_to_move: 'white' | 'black'
  attempts: number
  first_attempt_correct: boolean
  assisted_correct: boolean
  needed_retry: boolean
  recognized: boolean
  hint_level: number
  original: string
  target_squares: string[]
  seconds: number | null
}

export type PracticeSummary = {
  session_id: number
  mistake_type: 'M1' | 'M2'
  label: string
  assisted: boolean
  completed: number
  total: number
  first_attempt_correct: number
  assisted_correct: number
  needed_retry: number
  recognized: number
  repeat_games: boolean
  delayed_test: DelayedTestInfo
  items: SummaryItem[]
}

export type PracticeStatus = {
  unlocked: boolean
  positions: { unseen: number; to_repeat: number }
  session: { session_id: number; done: number; total: number } | null
  last_completed: number | null
}

const TINT = {
  lastMove: 'rgba(255, 215, 0, 0.45)',
  piece: 'rgba(255, 140, 0, 0.55)',
  danger: 'rgba(220, 60, 50, 0.6)',
  free: 'rgba(60, 170, 90, 0.6)',
}

/** Square tints and an arrow for the hints the player asked for (H1 the last move, H2 the piece, H3 the line's first move). */
export function hintMarks(hints: Hint[]): { squares: Record<string, string>; arrows: { startSquare: string; endSquare: string; color: string }[] } {
  const squares: Record<string, string> = {}
  const arrows: { startSquare: string; endSquare: string; color: string }[] = []
  for (const h of hints) {
    if (h.kind === 'last_move') for (const sq of h.squares ?? []) squares[sq] = TINT.lastMove
    if (h.kind === 'piece') for (const sq of h.squares ?? []) squares[sq] = TINT.piece
    if (h.kind === 'line' && h.uci?.[0]) {
      arrows.push({ startSquare: h.uci[0].slice(0, 2), endSquare: h.uci[0].slice(2, 4), color: 'rgba(60, 120, 220, 0.85)' })
    }
  }
  return { squares, arrows }
}

/** What the feedback board shows: the target piece (red if it is yours, green if it is theirs) and the line as arrows. */
export function feedbackMarks(fb: PracticeFeedback, fen: string, sideToMove: 'white' | 'black') {
  const squares: Record<string, string> = {}
  const mine = sideToMove === 'white' ? 'w' : 'b'
  for (const sq of fb.target_squares) squares[sq] = pieceColorAt(fen, sq) === mine ? TINT.danger : TINT.free
  const arrows = fb.board_line.slice(0, 2).map((uci, i) => ({
    startSquare: uci.slice(0, 2),
    endSquare: uci.slice(2, 4),
    color: i === 0 ? 'rgba(80, 140, 230, 0.8)' : 'rgba(220, 60, 50, 0.85)',
  }))
  return { squares, arrows }
}

/** The line a mistake allowed, in words for the caption under the board. */
export function lineCaption(type: 'M1' | 'M2'): string {
  return type === 'M1' ? 'Blue: your move in the game. Red: what it allowed.' : 'The arrow shows the free capture.'
}

/** Short instruction for each step, kept in one place so the page and its tests agree. */
export function stepTitle(stage: PracticeCurrent['stage'], type: 'M1' | 'M2'): string {
  if (stage === 'recognition') {
    return type === 'M1'
      ? '1. A question first. Which of YOUR pieces can the other side win? Tap it, or choose "No immediate threat".'
      : '1. A question first. Which of THEIR pieces can you win for free? Tap it, or choose "No immediate threat".'
  }
  if (stage === 'move') return '2. Your move. Click a piece, then the square it should go to. To castle, click your king, then the rook.'
  return '3. Feedback'
}

/** Next hint button text; null when all three rungs are used. */
export function hintButton(level: number): string | null {
  if (level >= 3) return null
  return level === 0 ? 'Give me a hint' : `Another hint (${level} of 3 used)`
}

/** The summary's lines (PRD §6.4). Practice is assisted, so nothing here is a test score. */
export function summaryLines(s: PracticeSummary): string[] {
  return [
    `Positions completed: ${s.completed} of ${s.total}`,
    `Right on the first try with no hint: ${s.first_attempt_correct}`,
    `Right on the first try with a hint: ${s.assisted_correct}`,
    `Needed another try: ${s.needed_retry}`,
    `Spotted the problem yourself, with no hint: ${s.recognized}`,
  ]
}

/** What the home card says about practice. */
export function practiceLabel(p: PracticeStatus): { button: string | null; note: string } {
  if (!p.unlocked) return { button: null, note: 'Take the starting test first. Practice unlocks after it.' }
  if (p.session) {
    return { button: `Continue practice (${p.session.done} of ${p.session.total} done)`, note: 'Practice is assisted: hints and feedback are on.' }
  }
  const left = p.positions.unseen + p.positions.to_repeat
  if (left < 3) return { button: null, note: `Not enough practice positions left (${left}; at least 3 are needed).` }
  return {
    button: 'Start practice',
    note: `${p.positions.unseen} new and ${p.positions.to_repeat} to repeat. Practice is assisted: hints and feedback are on.`,
  }
}

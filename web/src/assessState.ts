/**
 * Pure helpers for the unassisted test (PRD v2 §7). The server owns every answer and score; these only shape what the
 * player sees. Before the final submit the server sends the board and its legal moves, nothing else.
 */

export const NO_THREAT = 'none'

export type PoolStatus = {
  mistake_positions: number
  clean_positions: number
  needed_mistake_positions: number
  needed_clean_positions: number
  ready: boolean
}

export type HomeType = {
  mistake_type: 'M1' | 'M2'
  label: string
  pool: PoolStatus
  baseline: { assessment_id: number; status: 'pending' | 'in_progress' | 'submitted' } | null
}

export type AssessmentView = {
  assessment_id: number
  assessment_kind: 'BASELINE' | 'DELAYED'
  mistake_type: 'M1' | 'M2'
  label: string
  cue: string
  status: string
  total: number
  answered: number
  ready_to_submit: boolean
  current: {
    ord: number
    number: number
    fen: string
    side_to_move: 'white' | 'black'
    legal_moves: string[]
  } | null
}

export type MoveRef = { uci: string; san: string }

export type ResultItem = {
  number: number
  fen: string
  side_to_move: 'white' | 'black'
  kind: 'MISTAKE' | 'CLEAN'
  answer_squares: string[]
  your_tap: string
  tap_correct: boolean
  your_move: MoveRef
  move_sound: boolean
  correct: boolean
  explanation: string
  move_explanation: string
  good_moves: MoveRef[]
  game_move: MoveRef
  line: { uci: string[]; san: string[] } | null
  seconds: number | null
  interrupted: boolean
  recognition_chance: number
  move_chance: number | null
}

export type Results = {
  assessment_id: number
  mistake_type: 'M1' | 'M2'
  label: string
  total: number
  scores: { recognition: number; move: number; combined: number }
  chance: { recognition: number; move: number | null; combined: number | null }
  chance_pending: boolean
  interrupted: number
  items: ResultItem[]
}

/** What the start button says for a mistake type, or null when it cannot start. */
export function startLabel(t: HomeType): string | null {
  if (t.baseline?.status === 'submitted') return 'See my results'
  if (t.baseline) return 'Continue the test'
  return t.pool.ready ? 'Start the test' : null
}

/** "Not enough games yet" with the counts, when the pool is too small (PRD §5.2); null when it is big enough. */
export function poolShortfall(p: PoolStatus): string | null {
  if (p.ready) return null
  return (
    `Not enough games yet for this mistake type: ${p.mistake_positions} of ${p.needed_mistake_positions} mistake ` +
    `positions and ${p.clean_positions} of ${p.needed_clean_positions} positions with nothing wrong.`
  )
}

/** The piece letter on a square of a FEN board (FEN letters: upper case is White), or null for an empty square. */
export function pieceAt(fen: string, square: string): string | null {
  const rows = fen.split(' ')[0].split('/')
  const file = square.charCodeAt(0) - 97
  const rank = Number(square[1])
  if (square.length !== 2 || file < 0 || file > 7 || !(rank >= 1 && rank <= 8)) return null
  let col = 0
  for (const ch of rows[8 - rank]) {
    if (/\d/.test(ch)) {
      col += Number(ch)
      continue
    }
    if (col === file) return ch
    col += 1
  }
  return null
}

/** The piece colour on a square of a FEN board ('w' / 'b'), or null for an empty square. */
export function pieceColorAt(fen: string, square: string): 'w' | 'b' | null {
  const ch = pieceAt(fen, square)
  if (!ch) return null
  return ch === ch.toUpperCase() ? 'w' : 'b'
}

/** Clicking the king and then one of your own rooks means castling on that side, when it is legal. */
export function castleMove(legal: string[], fen: string, from: string, to: string): string | null {
  const king = pieceAt(fen, from)
  const rook = pieceAt(fen, to)
  if (!king || !rook || king.toLowerCase() !== 'k' || rook.toLowerCase() !== 'r') return null
  if (pieceColorAt(fen, from) !== pieceColorAt(fen, to) || from[1] !== to[1]) return null
  const step = to.charCodeAt(0) > from.charCodeAt(0) ? 2 : -2
  const target = String.fromCharCode(from.charCodeAt(0) + step) + from[1]
  return legal.includes(from + target) ? from + target : null
}

/** The legal move from `from` to `to` (a promotion becomes a queen), or null. */
export function pickMove(legal: string[], from: string, to: string): string | null {
  const candidates = legal.filter((m) => m.startsWith(from + to))
  if (candidates.length === 0) return null
  return candidates.find((m) => m.endsWith('q')) ?? candidates[0]
}

/** Squares a selected piece can move to (for the move dots). */
export function targetsFrom(legal: string[], from: string | null): string[] {
  if (!from) return []
  return legal.filter((m) => m.startsWith(from)).map((m) => m.slice(2, 4))
}

/** "3 of 5 (guessing would get about 0.9)" — a score always next to its random-guess rate (PRD §7.5). */
export function scoreLine(score: number, total: number, chance: number | null): string {
  const guess =
    chance === null ? 'guessing: still calculating'
      : chance < 0.05 ? 'guessing would get almost none'
        : `guessing would get about ${chance.toFixed(1)}`
  return `${score} of ${total} (${guess})`
}

/** The tap in words, for the results page. */
export function tapWords(tap: string): string {
  return tap === NO_THREAT ? '"No immediate threat"' : `the piece on ${tap}`
}

export type GameView = {
  id: string
  fen: string
  revision: number
  turn: 'white' | 'black'
  user_color: 'white' | 'black'
  mode: string
  assisted: boolean
  engine_level: number | null
  opponent?: 'stockfish' | 'maia3'
  opponent_elo?: number | null
  outcome: { result: string; termination: string } | null
  legal_moves: string[]
  moves: string[]
  can_take_back: boolean
  hints_used: number
}

/**
 * Decide which game state to show when a server response arrives.
 *
 * Responses can arrive out of order: the engine's reply is deliberately shown after a
 * delay, so a snapshot taken before a resignation, takeback or mode change can arrive
 * after the response to that action. Only a response for the game on screen whose
 * revision is not older than the one shown may replace it. The server bumps the revision
 * on every move, resignation, takeback and mode change.
 *
 * `replace` is for the player starting a new game, which always takes over the screen.
 */
export function acceptGame(
  current: GameView | null,
  incoming: GameView,
  replace = false,
): GameView {
  if (replace || current === null) return incoming
  if (incoming.id !== current.id) return current // a response for a game that was left behind
  return incoming.revision >= current.revision ? incoming : current
}

export type Feedback = {
  ply: number
  verdict: 'good' | 'slip' | 'mistake' | 'blunder'
  headline: string
  cost_pawns: number | null
  right: string[]
  wrong: string[]
  better_move: { uci: string; from: string; to: string; text: string } | null
  played: { uci: string; text: string }
  fen_before: string // the position the move was played in; the suggested move is only valid there
  marks: { own_hanging: Mark[]; missed_free: Mark[] } // squares the board can mark (engine-confirmed misses only)
  classification: { key: MoveClass; opening: string | null } // how the move is labelled on the board
}

export type MoveClass = 'book' | 'best' | 'good' | 'slip' | 'mistake' | 'blunder'

export type Mark = { square: string; piece: string } // piece = FEN letter, so a mark is drawn only while it is still there

/** Index of the user's most recent move in a normal game (White moves on even plies), or null. */
export function latestUserPly(moves: string[], userColor: 'white' | 'black'): number | null {
  for (let i = moves.length - 1; i >= 0; i--) {
    if ((i % 2 === 0) === (userColor === 'white')) return i
  }
  return null
}

/** Feedback as the page stores it: tied to the game and the exact moves it judged. */
export type StoredFeedback = Feedback & { gameId: string; prefix: string[] }

export function storeFeedback(fb: Feedback, gameId: string, moves: string[]): StoredFeedback {
  return { ...fb, gameId, prefix: moves.slice(0, fb.ply + 1) }
}

/**
 * Feedback is shown only for the game on screen, only while every move up to the one it judged is unchanged
 * (a takeback or a different line removes it), and only while that is still the user's latest move.
 */
export function feedbackIsCurrent(
  fb: StoredFeedback | null,
  gameId: string,
  moves: string[],
  userColor: 'white' | 'black',
): fb is StoredFeedback {
  if (fb === null || fb.gameId !== gameId) return false
  if (latestUserPly(moves, userColor) !== fb.ply) return false
  return fb.prefix.length === fb.ply + 1 && fb.prefix.every((m, i) => moves[i] === m)
}

export type Threats = {
  revision: number
  in_check: boolean
  threats: { kind: 'piece_can_be_taken' | 'mate_threat'; square?: string; capture?: string; text: string }[]
}

/** One red arrow per piece of yours the opponent can win: from the capturing piece to yours. */
export function threatArrows(t: Threats): { startSquare: string; endSquare: string; color: string }[] {
  return t.threats
    .filter((x) => x.kind === 'piece_can_be_taken' && x.capture && x.capture.length >= 4)
    .map((x) => ({ startSquare: x.capture!.slice(0, 2), endSquare: x.capture!.slice(2, 4), color: 'rgba(220, 60, 50, 0.85)' }))
}

/** Threat warnings belong to one position: show them only for the revision they were computed for. */
export function threatsAreCurrent(t: (Threats & { gameId: string }) | null, game: GameView): boolean {
  return t !== null && t.gameId === game.id && t.revision === game.revision && game.turn === game.user_color
}

export type Why = {
  ply: number
  played_uci: string
  status: 'verified' | 'repaired' | 'fallback' | 'unavailable'
  text: string
  note: string | null
}

/** Identifies the exact game and moves a piece of feedback (or its explanation) belongs to. */
export function feedbackKey(fb: StoredFeedback): string {
  return `${fb.gameId}:${fb.prefix.join(' ')}`
}

export function whyLabel(status: Why['status']): string {
  return status === 'verified' || status === 'repaired'
    ? 'Every claim in this explanation was checked by the engine and the rules.'
    : 'Limited to facts the engine and rules confirmed.'
}

/** The FEN letter of the piece on `square` in `fen`, or null when the square is empty or invalid. */
export function pieceAt(fen: string, square: string): string | null {
  const rows = fen.split(' ')[0].split('/')
  const file = square.charCodeAt(0) - 97
  const rank = Number(square[1])
  if (rows.length !== 8 || file < 0 || file > 7 || !(rank >= 1 && rank <= 8)) return null
  let col = 0
  for (const ch of rows[8 - rank]) {
    if (/\d/.test(ch)) col += Number(ch)
    else {
      if (col === file) return ch
      col += 1
    }
  }
  return null
}

/**
 * The feedback the page may show: only in Practice (it is assistance, and Play counts as real evidence), only for the game on
 * screen, and only while the move it judged is still the player's latest. Every coaching visual (verdict, board marks, hint
 * view, move badge) goes through this, so switching to Play removes them all at once.
 */
export function feedbackToShow(
  fb: StoredFeedback | null,
  game: Pick<GameView, 'id' | 'moves' | 'user_color' | 'mode'>,
): StoredFeedback | null {
  if (game.mode !== 'practice') return null
  return feedbackIsCurrent(fb, game.id, game.moves, game.user_color) ? fb : null
}

/**
 * Squares to mark on the live board after a suboptimal move: your own pieces that can be taken (red, and still red on the
 * square where one was taken after the opponent's reply) and free pieces you could have taken (green, only while the same
 * piece still stands there). Never marked after a good move.
 */
export function boardMarks(fen: string, fb: Pick<Feedback, 'verdict' | 'marks'>): { hanging: string[]; missed: string[] } {
  if (fb.verdict === 'good') return { hanging: [], missed: [] }
  const sameColour = (a: string, b: string) => (a === a.toUpperCase()) === (b === b.toUpperCase())
  const hanging = fb.marks.own_hanging
    .filter((m) => {
      const now = pieceAt(fen, m.square)
      return now === m.piece || (now !== null && !sameColour(now, m.piece)) // still there, or taken on this square
    })
    .map((m) => m.square)
  const missed = fb.marks.missed_free.filter((m) => pieceAt(fen, m.square) === m.piece).map((m) => m.square)
  return { hanging, missed }
}

/** Left arrow means Undo, unless the player is typing or choosing in a form control, or holds a modifier key. */
export function isUndoKey(e: { key: string; ctrlKey?: boolean; metaKey?: boolean; altKey?: boolean; shiftKey?: boolean }, targetTag: string, editable: boolean): boolean {
  if (e.key !== 'ArrowLeft' || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return false
  return !editable && !['INPUT', 'TEXTAREA', 'SELECT'].includes(targetTag.toUpperCase())
}

/** The badge shown on the square a move was played to, like the labels on chess sites. */
export function moveBadge(key: MoveClass, opening?: string | null): { symbol: string; label: string; tone: string } {
  const table: Record<MoveClass, { symbol: string; label: string; tone: string }> = {
    book: { symbol: '📖', label: opening ? `Book move: ${opening}` : 'Book move', tone: 'book' },
    best: { symbol: '★', label: 'Best move', tone: 'best' },
    good: { symbol: '👍', label: 'Good move', tone: 'good' },
    slip: { symbol: '?!', label: 'Inaccuracy: a small slip', tone: 'slip' },
    mistake: { symbol: '?', label: 'Mistake', tone: 'mistake' },
    blunder: { symbol: '??', label: 'Blunder', tone: 'blunder' },
  }
  return table[key]
}

const DRAW_REASONS: Record<string, string> = {
  stalemate: 'stalemate',
  insufficient_material: 'insufficient material',
  threefold_repetition: 'repetition',
  fivefold_repetition: 'repetition',
  fifty_moves: 'the 50-move rule',
  seventyfive_moves: 'the 75-move rule',
}

/** What to print on the board when the game ends; confetti only if the player won by checkmate. */
export function gameEndBanner(game: Pick<GameView, 'outcome' | 'user_color'>): { text: string; celebrate: boolean } | null {
  const o = game.outcome
  if (!o) return null
  if (o.result === '1/2-1/2') {
    const why = DRAW_REASONS[o.termination]
    return { text: why ? `Draw by ${why}` : 'Draw', celebrate: false }
  }
  const won = (o.result === '1-0' ? 'white' : 'black') === game.user_color
  if (o.termination === 'checkmate') {
    return won ? { text: 'Checkmate! You win', celebrate: true } : { text: 'Checkmated', celebrate: false }
  }
  if (o.termination === 'resignation') {
    return { text: won ? 'Opponent resigned' : 'You resigned', celebrate: false }
  }
  return { text: won ? 'You win' : 'You lose', celebrate: false }
}

export type HintStep = { level: number; kind: string; text: string; from?: string; to?: string; uci?: string }
export type Hint = { gameId: string; revision: number; level: number; maxLevel: number; steps: HintStep[]; hintsUsed: number }

/** The hint ladder is Practice-only help for the position on the board: show it for nothing else (rule 4). */
export function hintToShow(hint: Hint | null, game: Pick<GameView, 'id' | 'revision' | 'mode' | 'outcome'>): Hint | null {
  if (!hint || game.mode !== 'practice' || game.outcome) return null
  return hint.gameId === game.id && hint.revision === game.revision ? hint : null
}

/** "Stockfish Level 3" or "Maia-3 at 900": who the player is facing. The Elo is what the model is conditioned on, not a measured strength. */
export function opponentLabel(g: Pick<GameView, 'engine_level' | 'opponent' | 'opponent_elo'>): string {
  return g.opponent === 'maia3' ? `Maia-3 at ${g.opponent_elo}` : `Stockfish Level ${g.engine_level}`
}

/** Whether the machine plays the other side. A Maia-3 game has no engine_level, so test the opponent, not the level. */
export function hasEngineOpponent(g: Pick<GameView, 'engine_level' | 'opponent' | 'opponent_elo'>): boolean {
  return g.engine_level !== null || (g.opponent === 'maia3' && g.opponent_elo != null)
}

/** What a new page starts with: Maia-3 at 1600 when the server has it (owner's level, 2026-10-29; was 800), else Stockfish. */
export const DEFAULT_MAIA_ELO = 1600
export function startingOpponent(maiaAvailable: boolean): 'stockfish' | 'maia3' {
  return maiaAvailable ? 'maia3' : 'stockfish'
}

/**
 * Run `onSettled` once when the opponent probe finishes, unless the returned cancel function was called first.
 * React StrictMode replays the startup effect (setup, cleanup, setup), so the first run's continuation must go quiet:
 * otherwise two automatic first games start and the second replaces a game the player began meanwhile.
 */
export function probeOnce<T>(probe: () => Promise<T | null>, onSettled: (result: T | null) => void): () => void {
  let cancelled = false
  void probe()
    .catch(() => null)
    .then((result) => {
      if (!cancelled) onSettled(result)
    })
  return () => {
    cancelled = true
  }
}

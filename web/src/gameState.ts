export type GameView = {
  id: string
  fen: string
  revision: number
  turn: 'white' | 'black'
  user_color: 'white' | 'black'
  mode: string
  assisted: boolean
  engine_level: number | null
  outcome: { result: string; termination: string } | null
  legal_moves: string[]
  moves: string[]
  takebacks_left: number
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
}

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
  threats: { kind: 'piece_can_be_taken' | 'mate_threat'; square?: string; text: string }[]
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

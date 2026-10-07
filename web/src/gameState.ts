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
  cost_pawns: number
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

/** Feedback is only shown while the move it judges is still on the board (a takeback removes it). */
export function feedbackIsCurrent(fb: Feedback | null, moves: string[]): fb is Feedback {
  return fb !== null && moves[fb.ply] === fb.played.uci
}

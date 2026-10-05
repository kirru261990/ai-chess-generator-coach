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

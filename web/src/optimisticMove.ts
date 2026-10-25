import type { GameBackend, GamePayload } from './gameBackend'

export const ENGINE_MIN_REPLY_MS = 1000 // as in the web app: the player's move stays alone on the board this long before the reply

export type MoveHooks = {
  pending: (uci: string | null) => void // the move to draw now, before the server answers (null: stop drawing it)
  payload: (p: GamePayload) => void // a position the server confirmed
  status: (label: string | null) => void
  now?: () => number
  sleep?: (ms: number) => Promise<void>
}

/**
 * The player's move on the chat board. The move is drawn at the click (`pending`), then the server confirms it (`backend.move`), and
 * its position replaces the drawn one. A refusal (stale, illegal, game over) takes the drawn move off the board and returns the server's
 * sentence. The engine's reply is requested as soon as the move is confirmed but drawn no sooner than ENGINE_MIN_REPLY_MS after the click.
 * Returns an error sentence, or null.
 */
export async function playMove(
  backend: GameBackend,
  game: { id: string; revision: number },
  uci: string,
  hooks: MoveHooks,
): Promise<string | null> {
  const now = hooks.now ?? Date.now
  const sleep = hooks.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)))
  const clicked = now()
  hooks.pending(uci)
  hooks.status('Sending your move…')
  try {
    let first: GamePayload
    try {
      first = await backend.move(game.id, uci, game.revision)
    } catch (e) {
      hooks.pending(null) // undo the drawn move
      return (e as Error).message
    }
    hooks.payload(first)
    hooks.pending(null)
    if (first.game.outcome) {
      // A move that ends the game has no reply, but Practice still owes its verdict: the engine step plays nothing then and carries it.
      if (first.game.mode === 'practice') hooks.payload(await backend.engineMove(first.game.id, first.game.revision))
      return null
    }
    if (first.game.turn === first.game.user_color) return null
    hooks.status('Stockfish is thinking…')
    // Practice: the verdict comes first, then the reply is asked for. One engine does one search at a time, so asking for both at once
    // made them land together; this way the verdict shows when its own search ends. If it fails, the reply carries the same verdict
    // (the server searches once and keeps it), so nothing depends on this call.
    if (first.game.mode === 'practice') {
      try {
        hooks.payload(await backend.judge(first.game.id, first.game.revision))
      } catch {
        /* the reply step carries the verdict */
      }
    }
    const reply = await backend.engineMove(first.game.id, first.game.revision)
    const wait = ENGINE_MIN_REPLY_MS - (now() - clicked)
    if (wait > 0) await sleep(wait)
    hooks.payload(reply)
    return null
  } catch (e) {
    return (e as Error).message
  } finally {
    hooks.status(null)
  }
}

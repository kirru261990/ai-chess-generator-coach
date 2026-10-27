import type { Feedback, GameView, Hint, HintStep, Threats } from './gameState'
import type { ToolCaller } from './practiceBackend'

/** What a game tool returns as structured data (see `backend/app/mcp/game_tools.py`, ADR 0009). The `game` part is the same for Play
 *  and Practice. Everything that helps the player is under `practice`, which a Play game never has. */
export type GameData = Pick<
  GameView,
  'id' | 'fen' | 'moves' | 'revision' | 'turn' | 'user_color' | 'mode' | 'engine_level' | 'opponent' | 'opponent_elo' | 'outcome' | 'legal_moves'
>
export type PracticeExtras = {
  assisted: boolean
  hints_used: number
  can_take_back: boolean
  show_threats: boolean
  threats: Threats | null
  feedback: (Feedback & { prefix: string[] }) | null
  hint: { revision: number; level: number; max_level: number; steps: HintStep[]; hints_used: number } | null
}
export type GamePayload = { kind: 'game'; game: GameData; practice?: PracticeExtras }

export const isGamePayload = (x: unknown): x is GamePayload =>
  !!x && (x as GamePayload).kind === 'game' && typeof (x as GamePayload).game?.id === 'string'

/** The help the page may draw: only for a Practice game (rule 4). In Play this is always null, whatever the payload holds. */
export function practiceOnly(p: GamePayload): PracticeExtras | null {
  return p.game.mode === 'practice' && p.practice ? p.practice : null
}

/** The page's `GameView`, built from the allow-listed data; the Practice-only fields stay at their Play values in Play. */
export function toGameView(p: GamePayload): GameView {
  const x = practiceOnly(p)
  return { ...p.game, assisted: x?.assisted ?? false, can_take_back: x?.can_take_back ?? false, hints_used: x?.hints_used ?? 0 }
}

export function toHint(p: GamePayload): Hint | null {
  const x = practiceOnly(p)
  const h = x?.hint
  return h ? { gameId: p.game.id, revision: h.revision, level: h.level, maxLevel: h.max_level, steps: h.steps, hintsUsed: h.hints_used } : null
}

/** Where the game page gets its data. The chat board turns each step into a game tool call. Each step resolves to the new state. */
export type GameBackend = {
  show(id: string): Promise<GamePayload>
  /** Only the player's move, returned at once with the position after it (the engine has not replied). */
  move(id: string, uci: string, revision: number): Promise<GamePayload>
  /** Stockfish's reply to the move just shown; `revision` is the position the page is showing. Plays nothing if that is out of date. */
  engineMove(id: string, revision: number): Promise<GamePayload>
  /** The verdict on the move just shown, without the reply (Practice only has one), so it can be drawn before the engine answers. */
  judge(id: string, revision: number): Promise<GamePayload>
  resign(id: string): Promise<GamePayload>
  undo(id: string): Promise<GamePayload>
  hint(id: string, level: number): Promise<GamePayload>
  threats(id: string, show: boolean): Promise<GamePayload>
}

/** The game page over the chat tools. A refused step has only text, which becomes the error shown on the page. */
export function gameToolBackend(call: ToolCaller): GameBackend {
  const run = async (name: string, args: Record<string, unknown>): Promise<GamePayload> => {
    const { structured, text } = await call(name, args)
    if (!isGamePayload(structured)) throw new Error(text.replace(/^I could not do that: /, '') || 'that did not work')
    return structured
  }
  return {
    show: (id) => run('game_show', { game_id: id }),
    move: (id, uci, revision) => run('game_apply_move', { game_id: id, move: uci, expected_revision: revision }),
    engineMove: (id, revision) => run('game_engine_move', { game_id: id, expected_revision: revision }),
    judge: (id, revision) => run('game_judge', { game_id: id, expected_revision: revision }),
    resign: (id) => run('game_resign', { game_id: id }),
    undo: (id) => run('game_undo', { game_id: id }),
    hint: (id, level) => run('game_hint', { game_id: id, level }),
    threats: (id, show) => run('game_threats', { game_id: id, show }),
  }
}

import { describe, expect, it } from 'vitest'
import { gameToolBackend, isGamePayload, practiceOnly, toGameView, toHint, type GamePayload } from './gameBackend'

const game = (mode: string) => ({
  id: 'g1', fen: 'start', moves: [], revision: 0, turn: 'white' as const, user_color: 'white' as const, mode,
  engine_level: 3, outcome: null, legal_moves: ['e2e4'],
})
const extras = {
  assisted: true, hints_used: 2, can_take_back: true, show_threats: true,
  threats: { revision: 0, in_check: false, threats: [] }, feedback: null,
  hint: { revision: 0, level: 2, max_level: 5, steps: [{ level: 2, kind: 'cue', text: 'x' }], hints_used: 2 },
}

describe('the game page backend over chat tools', () => {
  it('turns each step into one game tool call', async () => {
    const calls: [string, Record<string, unknown>][] = []
    const payload: GamePayload = { kind: 'game', game: game('play') }
    const b = gameToolBackend(async (name, args) => (calls.push([name, args]), { structured: payload, text: '' }))
    await b.show('g1')
    await b.move('g1', 'e2e4', 4)
    await b.engineMove('g1', 5)
    await b.resign('g1')
    await b.undo('g1')
    await b.hint('g1', 3)
    await b.threats('g1', false)
    expect(calls).toEqual([
      ['game_show', { game_id: 'g1' }],
      ['game_apply_move', { game_id: 'g1', move: 'e2e4', expected_revision: 4 }],
      ['game_engine_move', { game_id: 'g1', expected_revision: 5 }],
      ['game_resign', { game_id: 'g1' }],
      ['game_undo', { game_id: 'g1' }],
      ['game_hint', { game_id: 'g1', level: 3 }],
      ['game_threats', { game_id: 'g1', show: false }],
    ])
  })

  it('shows a refusal as the error, without the prefix', async () => {
    const b = gameToolBackend(async () => ({ structured: null, text: 'I could not do that: that help is only available in Practice mode.' }))
    await expect(b.hint('g1', 1)).rejects.toThrow('that help is only available in Practice mode.')
  })

  it('recognises a game payload and nothing else', () => {
    expect(isGamePayload({ kind: 'game', game: game('play') })).toBe(true)
    expect(isGamePayload({ view: {}, summary: null })).toBe(false)
    expect(isGamePayload(null)).toBe(false)
  })

  it('ignores any help in a Play payload (rule 4)', () => {
    const p: GamePayload = { kind: 'game', game: game('play'), practice: extras }
    expect(practiceOnly(p)).toBeNull()
    expect(toHint(p)).toBeNull()
    expect(toGameView(p)).toMatchObject({ assisted: false, can_take_back: false, hints_used: 0 })
  })

  it('reads the help from a Practice payload', () => {
    const p: GamePayload = { kind: 'game', game: game('practice'), practice: extras }
    expect(practiceOnly(p)).toBe(extras)
    expect(toHint(p)).toMatchObject({ gameId: 'g1', level: 2, maxLevel: 5, hintsUsed: 2 })
    expect(toGameView(p)).toMatchObject({ assisted: true, can_take_back: true, hints_used: 2 })
  })
})

describe('a Maia-3 game in the chat board', () => {
  it('keeps the opponent fields, so the board can name Maia and know the engine plays', () => {
    const p: GamePayload = { kind: 'game', game: { ...game('play'), engine_level: null, opponent: 'maia3', opponent_elo: 900 } }
    expect(toGameView(p)).toMatchObject({ engine_level: null, opponent: 'maia3', opponent_elo: 900 })
  })
})

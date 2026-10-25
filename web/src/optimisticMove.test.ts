import { describe, expect, it } from 'vitest'
import type { GameBackend, GamePayload } from './gameBackend'
import { ENGINE_MIN_REPLY_MS, playMove } from './optimisticMove'

const pay = (revision: number, turn: 'white' | 'black', mode = 'play', outcome: GamePayload['game']['outcome'] = null): GamePayload => ({
  kind: 'game',
  game: { id: 'g', fen: 'f', moves: [], revision, turn, user_color: 'white', mode, engine_level: 1, outcome, legal_moves: [] },
})

function harness(backend: Partial<GameBackend>) {
  const events: string[] = []
  let t = 0
  const hooks = {
    pending: (u: string | null) => events.push(`pending:${u}`),
    payload: (p: GamePayload) => events.push(`payload:r${p.game.revision}`),
    status: (s: string | null) => events.push(`status:${s}`),
    now: () => t,
    sleep: async (ms: number) => { events.push(`sleep:${ms}`); t += ms },
  }
  return { events, hooks, tick: (ms: number) => (t += ms), backend: backend as GameBackend }
}

describe('the players move on the chat board', () => {
  it('draws the move before any call, then confirms it, then draws the reply no sooner than 1 s after the click', async () => {
    const h = harness({ move: async () => (h.tick(300), pay(1, 'black')), engineMove: async () => (h.tick(100), pay(2, 'white')) })
    expect(await playMove(h.backend, { id: 'g', revision: 0 }, 'e2e4', h.hooks)).toBeNull()
    expect(h.events).toEqual(['pending:e2e4', 'status:Sending your move…', 'payload:r1', 'pending:null', 'status:Stockfish is thinking…',
      `sleep:${ENGINE_MIN_REPLY_MS - 400}`, 'payload:r2', 'status:null'])
  })
  it('does not wait again when the reply is already late', async () => {
    const h = harness({ move: async () => (h.tick(900), pay(1, 'black')), engineMove: async () => (h.tick(600), pay(2, 'white')) })
    await playMove(h.backend, { id: 'g', revision: 0 }, 'e2e4', h.hooks)
    expect(h.events.some((e) => e.startsWith('sleep'))).toBe(false)
  })
  it('takes the drawn move off the board and returns the server sentence when the move is refused', async () => {
    const h = harness({ move: async () => { throw new Error('the board changed since you looked.') }, engineMove: async () => { throw new Error('no') } })
    expect(await playMove(h.backend, { id: 'g', revision: 0 }, 'e2e4', h.hooks)).toBe('the board changed since you looked.')
    expect(h.events).toEqual(['pending:e2e4', 'status:Sending your move…', 'pending:null', 'status:null'])
  })
  it('asks Practice for the verdict when the move ends the game, and Play does not', async () => {
    const calls: string[] = []
    const over = { result: '1/2-1/2', termination: 'stalemate' }
    for (const mode of ['practice', 'play']) {
      const h = harness({ move: async () => pay(1, 'black', mode, over), engineMove: async () => (calls.push(mode), pay(1, 'black', mode, over)) })
      await playMove(h.backend, { id: 'g', revision: 0 }, 'b6', h.hooks)
    }
    expect(calls).toEqual(['practice'])
  })
})

describe('the verdict on the chat board', () => {
  it('Practice asks for the verdict at the same time as the reply and draws it before the reply', async () => {
    const h = harness({
      move: async () => pay(1, 'black', 'practice'),
      judge: async () => (h.tick(200), pay(1, 'black', 'practice')),
      engineMove: async () => (h.tick(400), pay(2, 'white', 'practice')),
    })
    await playMove(h.backend, { id: 'g', revision: 0 }, 'e2e4', h.hooks)
    const shown = h.events.filter((e) => e.startsWith('payload'))
    expect(shown).toEqual(['payload:r1', 'payload:r1', 'payload:r2']) // the move, the verdict, the reply
  })
  it('Play never asks for a verdict', async () => {
    let asked = false
    const h = harness({ move: async () => pay(1, 'black', 'play'), judge: async () => ((asked = true), pay(1, 'black', 'play')), engineMove: async () => pay(2, 'white', 'play') })
    await playMove(h.backend, { id: 'g', revision: 0 }, 'e2e4', h.hooks)
    expect(asked).toBe(false)
  })
  it('a failed verdict call changes nothing: the reply still arrives', async () => {
    const h = harness({
      move: async () => pay(1, 'black', 'practice'),
      judge: async () => { throw new Error('boom') },
      engineMove: async () => pay(2, 'white', 'practice'),
    })
    expect(await playMove(h.backend, { id: 'g', revision: 0 }, 'e2e4', h.hooks)).toBeNull()
    expect(h.events).toContain('payload:r2')
  })
})

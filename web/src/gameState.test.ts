import { describe, expect, it } from 'vitest'
import { acceptGame, type GameView } from './gameState'

const game = (over: Partial<GameView> = {}): GameView => ({
  id: 'g1',
  fen: 'start',
  revision: 0,
  turn: 'white',
  user_color: 'white',
  mode: 'play',
  assisted: false,
  engine_level: 3,
  outcome: null,
  legal_moves: [],
  moves: [],
  takebacks_left: 0,
  ...over,
})

describe('acceptGame', () => {
  it('shows the first game it receives', () => {
    expect(acceptGame(null, game()).id).toBe('g1')
  })

  it('keeps a resignation when the older engine snapshot arrives late', () => {
    // revision 2: engine replied; revision 3: the player resigned during the display delay
    const resigned = game({ revision: 3, outcome: { result: '0-1', termination: 'resignation' } })
    const lateEngineSnapshot = game({ revision: 2 })
    const shown = acceptGame(resigned, lateEngineSnapshot)
    expect(shown.revision).toBe(3)
    expect(shown.outcome).toEqual({ result: '0-1', termination: 'resignation' })
  })

  it('keeps Practice and the assisted flag when an older Play snapshot arrives late', () => {
    const practice = game({ revision: 3, mode: 'practice', assisted: true })
    const lateSnapshot = game({ revision: 2, mode: 'play', assisted: false })
    const shown = acceptGame(practice, lateSnapshot)
    expect(shown.mode).toBe('practice')
    expect(shown.assisted).toBe(true)
  })

  it('keeps a takeback when an older snapshot arrives late', () => {
    const afterUndo = game({ revision: 5, moves: [] })
    const older = game({ revision: 4, moves: ['e2e4', 'e7e5'] })
    expect(acceptGame(afterUndo, older).moves).toEqual([])
  })

  it('accepts a newer or equal revision for the same game', () => {
    const current = game({ revision: 2 })
    expect(acceptGame(current, game({ revision: 3, fen: 'later' })).fen).toBe('later')
    expect(acceptGame(current, game({ revision: 2, fen: 'same' })).fen).toBe('same')
  })

  it('ignores a response for a game the player has left', () => {
    const newGame = game({ id: 'g2', revision: 0 })
    const oldGameReply = game({ id: 'g1', revision: 9 })
    expect(acceptGame(newGame, oldGameReply).id).toBe('g2')
  })

  it('lets a new game replace whatever is on screen, whatever its revision', () => {
    const current = game({ id: 'g1', revision: 9 })
    expect(acceptGame(current, game({ id: 'g2', revision: 0 }), true).id).toBe('g2')
  })
})

import { feedbackIsCurrent, latestUserPly, type Feedback } from './gameState'

describe('practice feedback helpers', () => {
  const fb = { ply: 2, played: { uci: 'g1f3', text: '' } } as Feedback

  it('finds the latest move of the user, whichever colour they play', () => {
    expect(latestUserPly([], 'white')).toBeNull()
    expect(latestUserPly(['e2e4'], 'black')).toBeNull()
    expect(latestUserPly(['e2e4', 'e7e5', 'g1f3'], 'white')).toBe(2)
    expect(latestUserPly(['e2e4', 'e7e5', 'g1f3'], 'black')).toBe(1)
  })

  it('hides feedback once the move it judged is taken back or replaced', () => {
    expect(feedbackIsCurrent(fb, ['e2e4', 'e7e5', 'g1f3'])).toBe(true)
    expect(feedbackIsCurrent(fb, ['e2e4', 'e7e5'])).toBe(false)
    expect(feedbackIsCurrent(fb, ['e2e4', 'e7e5', 'b1c3'])).toBe(false)
    expect(feedbackIsCurrent(null, [])).toBe(false)
  })
})

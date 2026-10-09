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
  can_take_back: false,
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

import { feedbackIsCurrent, latestUserPly, storeFeedback, type Feedback } from './gameState'

describe('practice feedback helpers', () => {
  const judged = ['e2e4', 'e7e5', 'g1f3']
  const fb = storeFeedback({ ply: 2, played: { uci: 'g1f3', text: '' } } as Feedback, 'g1', judged)

  it('finds the latest move of the user, whichever colour they play', () => {
    expect(latestUserPly([], 'white')).toBeNull()
    expect(latestUserPly(['e2e4'], 'black')).toBeNull()
    expect(latestUserPly(judged, 'white')).toBe(2)
    expect(latestUserPly(judged, 'black')).toBe(1)
  })

  it('shows feedback for the exact moves it judged', () => {
    expect(feedbackIsCurrent(fb, 'g1', judged, 'white')).toBe(true)
  })

  it('hides feedback after a takeback, a different move, or a newer move', () => {
    expect(feedbackIsCurrent(fb, 'g1', ['e2e4', 'e7e5'], 'white')).toBe(false)
    expect(feedbackIsCurrent(fb, 'g1', ['e2e4', 'e7e5', 'b1c3'], 'white')).toBe(false)
    expect(feedbackIsCurrent(fb, 'g1', [...judged, 'b8c6', 'f1c4'], 'white')).toBe(false)
  })

  it('hides feedback from another game or another line with the same last move', () => {
    expect(feedbackIsCurrent(fb, 'g2', judged, 'white')).toBe(false)
    expect(feedbackIsCurrent(fb, 'g1', ['d2d4', 'd7d5', 'g1f3'], 'white')).toBe(false)
    expect(feedbackIsCurrent(null, 'g1', [], 'white')).toBe(false)
  })
})

import { threatsAreCurrent, type Threats } from './gameState'

describe('threat warnings', () => {
  const t = { gameId: 'g1', revision: 4, in_check: false, threats: [] } as Threats & { gameId: string }
  const g = (over: Partial<GameView>) => game({ id: 'g1', revision: 4, turn: 'white', user_color: 'white', ...over })

  it('are shown only for the position they were computed for', () => {
    expect(threatsAreCurrent(t, g({}))).toBe(true)
    expect(threatsAreCurrent(t, g({ revision: 5 }))).toBe(false)
    expect(threatsAreCurrent(t, g({ id: 'g2' }))).toBe(false)
    expect(threatsAreCurrent(t, g({ turn: 'black' }))).toBe(false)
    expect(threatsAreCurrent(null, g({}))).toBe(false)
  })
})

import { feedbackKey, whyLabel } from './gameState'

describe('coach explanation helpers', () => {
  it('keys an explanation to its game and exact moves', () => {
    const a = storeFeedback({ ply: 0 } as Feedback, 'g1', ['e2e4'])
    const b = storeFeedback({ ply: 0 } as Feedback, 'g1', ['d2d4'])
    const c = storeFeedback({ ply: 0 } as Feedback, 'g2', ['e2e4'])
    expect(new Set([feedbackKey(a), feedbackKey(b), feedbackKey(c)]).size).toBe(3)
  })

  it('says plainly how far an explanation was checked', () => {
    expect(whyLabel('verified')).toMatch(/checked/)
    expect(whyLabel('repaired')).toMatch(/checked/)
    expect(whyLabel('fallback')).toMatch(/Limited/)
    expect(whyLabel('unavailable')).toMatch(/Limited/)
  })
})

import { boardMarks, isUndoKey, pieceAt } from './gameState'

describe('board marks after a suboptimal move', () => {
  const fen = '4k3/8/8/3n4/4N3/8/8/3RK3 w - - 0 1'
  const fb = (verdict: 'good' | 'slip' | 'mistake' | 'blunder') => ({
    verdict,
    marks: { own_hanging: [{ square: 'e4', piece: 'N' }], missed_free: [{ square: 'd5', piece: 'n' }] },
  })

  it('reads pieces from a FEN', () => {
    expect(pieceAt(fen, 'e4')).toBe('N')
    expect(pieceAt(fen, 'd5')).toBe('n')
    expect(pieceAt(fen, 'a1')).toBeNull()
    expect(pieceAt(fen, 'z9')).toBeNull()
  })

  it('marks your hanging piece red and the missed free piece green', () => {
    expect(boardMarks(fen, fb('mistake'))).toEqual({ hanging: ['e4'], missed: ['d5'] })
    expect(boardMarks(fen, fb('slip'))).toEqual({ hanging: ['e4'], missed: ['d5'] })
  })

  it('never marks after a good move', () => {
    expect(boardMarks(fen, fb('good'))).toEqual({ hanging: [], missed: [] })
  })

  it('keeps a red mark on the square where your piece was taken, and drops the green one when the free piece moved', () => {
    const taken = '4k3/8/8/3n4/4n3/8/8/3RK3 w - - 0 1' // a black knight captured on e4; the free knight is still on d5
    expect(boardMarks(taken, fb('blunder'))).toEqual({ hanging: ['e4'], missed: ['d5'] })
    const gone = '4k3/8/8/8/8/8/8/3RK3 w - - 0 1' // both squares empty: nothing left to mark
    expect(boardMarks(gone, fb('blunder'))).toEqual({ hanging: [], missed: [] })
  })

  it('drops a mark when a different piece of your own colour now stands there', () => {
    const other = '4k3/8/8/3n4/4B3/8/8/3RK3 w - - 0 1'
    expect(boardMarks(other, fb('blunder')).hanging).toEqual([])
    const swapped = '4k3/8/8/3N4/4N3/8/8/3RK3 w - - 0 1' // d5 now holds a different piece
    expect(boardMarks(swapped, fb('blunder')).missed).toEqual([])
  })
})

describe('left arrow means Undo', () => {
  it('only for a plain left arrow outside form controls', () => {
    expect(isUndoKey({ key: 'ArrowLeft' }, 'BODY', false)).toBe(true)
    expect(isUndoKey({ key: 'ArrowRight' }, 'BODY', false)).toBe(false)
    expect(isUndoKey({ key: 'ArrowLeft', metaKey: true }, 'BODY', false)).toBe(false)
    expect(isUndoKey({ key: 'ArrowLeft', shiftKey: true }, 'BODY', false)).toBe(false)
    for (const tag of ['TEXTAREA', 'input', 'SELECT']) expect(isUndoKey({ key: 'ArrowLeft' }, tag, false)).toBe(false)
    expect(isUndoKey({ key: 'ArrowLeft' }, 'DIV', true)).toBe(false)
  })
})

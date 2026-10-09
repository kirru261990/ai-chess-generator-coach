import { describe, expect, it } from 'vitest'
import { evalLabel, evalWords, whiteShare } from './evaluation'
import { arrowStillFits } from './gameState'

const cp = (n: number) => ({ cp: n, mate: null, mate_sign: null })
const mate = (n: number, sign: number) => ({ cp: null, mate: n, mate_sign: sign })

describe('whiteShare', () => {
  it('is half for an equal position and grows with White’s advantage', () => {
    expect(whiteShare(cp(0))).toBeCloseTo(0.5)
    expect(whiteShare(cp(100))).toBeGreaterThan(0.55)
    expect(whiteShare(cp(300))).toBeGreaterThan(whiteShare(cp(100)))
    expect(whiteShare(cp(-300))).toBeCloseTo(1 - whiteShare(cp(300)))
  })

  it('never reaches 0 or 1 for a plain score, but a mate fills the bar for the side that mates', () => {
    expect(whiteShare(cp(5000))).toBeLessThan(1)
    expect(whiteShare(mate(3, 1))).toBe(1)
    expect(whiteShare(mate(-2, -1))).toBe(0)
    expect(whiteShare(mate(0, -1))).toBe(0) // already checkmated: sign says who won
  })
})

describe('labels and words', () => {
  it('shows pawns with a sign, and mates as M<n>', () => {
    expect(evalLabel(cp(140))).toBe('+1.4')
    expect(evalLabel(cp(-30))).toBe('-0.3')
    expect(evalLabel(cp(0))).toBe('+0.0')
    expect(evalLabel(mate(-4, -1))).toBe('M4')
    expect(evalLabel(mate(0, 1))).toBe('1-0')
  })

  it('says it in plain words', () => {
    expect(evalWords(cp(10))).toBe('The position is about equal')
    expect(evalWords(cp(60))).toBe('White is slightly better')
    expect(evalWords(cp(-180))).toBe('Black is better')
    expect(evalWords(cp(-400))).toBe('Black is much better')
    expect(evalWords(cp(900))).toBe('White is winning')
    expect(evalWords(mate(3, -1))).toBe('Black can force checkmate in 3')
  })
})

describe('arrowStillFits', () => {
  const start = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
  it('needs a piece of the player’s colour on the starting square', () => {
    expect(arrowStillFits(start, 'e2', 'white')).toBe(true)
    expect(arrowStillFits(start, 'e7', 'white')).toBe(false) // an enemy pawn
    expect(arrowStillFits(start, 'e7', 'black')).toBe(true)
    expect(arrowStillFits(start, 'e4', 'white')).toBe(false) // empty
  })

  it('reads counted gaps in a position', () => {
    const fen = 'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2'
    expect(arrowStillFits(fen, 'e4', 'white')).toBe(true)
    expect(arrowStillFits(fen, 'e5', 'black')).toBe(true)
    expect(arrowStillFits(fen, 'e2', 'white')).toBe(false)
  })

  it('rejects nonsense squares', () => {
    expect(arrowStillFits(start, 'z9', 'white')).toBe(false)
    expect(arrowStillFits(start, 'e0', 'white')).toBe(false)
  })
})

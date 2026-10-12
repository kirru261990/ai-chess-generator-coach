import { describe, expect, it } from 'vitest'
import { summarise, summaryLines, uciForClick, type ItemOutcome } from './trainState'

const o = (p: Partial<ItemOutcome>): ItemOutcome => ({ index: 0, kind: 'own', correct: true, firstTry: true, assisted: false, gaveUp: false, ...p })

describe('uciForClick', () => {
  it('builds a plain move', () => expect(uciForClick('e2', 'e4', 'wP')).toBe('e2e4'))
  it('queens a pawn that reaches the last rank', () => {
    expect(uciForClick('a7', 'a8', 'wP')).toBe('a7a8q')
    expect(uciForClick('h2', 'h1', 'bP')).toBe('h2h1q')
  })
  it('does not add a promotion for other pieces', () => expect(uciForClick('a1', 'a8', 'wR')).toBe('a1a8'))
})

describe('summarise', () => {
  const outcomes = [
    o({ index: 0 }),
    o({ index: 1, assisted: true }),
    o({ index: 2, correct: false, firstTry: false, gaveUp: true, assisted: true }),
    o({ index: 3, kind: 'practice', correct: false }),
    o({ index: 4, kind: 'held_out', correct: true }),
  ]
  it('counts first tries, clean first tries, give-ups and the test', () => {
    expect(summarise(outcomes)).toEqual({ practiceTotal: 4, firstTryCorrect: 2, firstTryCleanCorrect: 1, gaveUp: 1, heldOut: 'passed' })
  })
  it('reads out counts with their denominators', () => {
    expect(summaryLines(summarise(outcomes))).toEqual([
      '2 of 4 practice positions right on the first try (1 with no hints)',
      '1 shown the answer',
      'Test position: passed',
    ])
  })
  it('says not tried when the test was skipped', () => expect(summarise([o({})]).heldOut).toBe('not tried'))
})

import { rapidLines, remainingMs, type RapidSummary } from './trainState'

describe('rapid helpers', () => {
  it('counts the time left and never goes below zero', () => {
    expect(remainingMs(10, 2500)).toBe(7500)
    expect(remainingMs(10, 12000)).toBe(0)
  })
  it('summarises by kind with counts, leaving out kinds not met', () => {
    const zero = { attempts: 0, correct: 0, timed_out: 0, careless: 0, median_seconds: null }
    const s: RapidSummary = {
      attempts: 7,
      by_kind: {
        hang: { attempts: 5, correct: 2, timed_out: 1, careless: 1, median_seconds: 6.04 },
        free: zero,
        calm: { attempts: 2, correct: 2, timed_out: 0, careless: 0, median_seconds: 3.5 },
        test: zero,
      },
    }
    expect(rapidLines(s)).toEqual([
      'A piece of yours could be taken: 2 of 5 right, 1 out of time, median 6.0 s',
      'Nothing needed doing: 2 of 2 right, median 3.5 s',
    ])
  })
})

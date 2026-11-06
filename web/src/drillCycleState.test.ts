import { describe, expect, it } from 'vitest'
import { compareLine, formatDuration, matchLine, nextGoal, type CycleRow } from './drillCycleState'

const row = (o: Partial<CycleRow> = {}): CycleRow => ({
  number: 2, finished: true, answered: 50, total: 50, matched: 40, total_ms: 600_000, median_ms: 11_000, chance: 0.04, ...o,
})

describe('formatDuration', () => {
  it('uses seconds under a minute and minutes after', () => {
    expect(formatDuration(38_400)).toBe('38 s')
    expect(formatDuration(252_000)).toBe('4 min 12 s')
    expect(formatDuration(120_000)).toBe('2 min')
  })
})

describe('matchLine', () => {
  it('always shows the denominator and the random-guess level', () => {
    expect(matchLine(row())).toBe('40 of 50 matched (a random legal move would match about 4%)')
    expect(matchLine(row({ chance: null }))).toBe('40 of 50 matched')
  })
})

describe('compareLine', () => {
  it('says faster or slower together with the matched change', () => {
    expect(compareLine(row({ vs_previous: { total_ms: -420_000, matched: 3, same_size: true } }))).toBe('7 min faster than cycle 1, 3 more matched')
    expect(compareLine(row({ vs_previous: { total_ms: 90_000, matched: -2, same_size: true } }))).toBe('1 min 30 s slower than cycle 1, 2 fewer matched')
  })
  it('says nothing for an unfinished cycle or a different size', () => {
    expect(compareLine(row({ finished: false, vs_previous: { total_ms: -1, matched: 0, same_size: true } }))).toBeNull()
    expect(compareLine(row({ vs_previous: { total_ms: -9000, matched: 1, same_size: false } }))).toBeNull()
    expect(compareLine(row())).toBeNull()
  })
})

describe('nextGoal', () => {
  it('pairs the time to beat with the matches to keep', () => {
    expect(nextGoal([row({ number: 1 })])).toContain('beat 10 min and keep at least 40 of 50')
  })
  it('is empty before a cycle is finished', () => {
    expect(nextGoal([row({ finished: false })])).toBeNull()
    expect(nextGoal([])).toBeNull()
  })
})

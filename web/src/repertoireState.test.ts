import { describe, expect, it } from 'vitest'
import { answerBanner, historyText, openingCard, summaryText, type OpeningRow } from './repertoireState'

const row = (o: Partial<OpeningRow> = {}): OpeningRow => ({
  key: 'caro_kann',
  name: 'Caro-Kann Defence',
  side: 'black',
  available: true,
  lines: 40,
  nodes_ours: 80,
  nodes_seen: 12,
  hits: 30,
  misses: 10,
  games: 900,
  stopped: 0,
  unchecked: false,
  ...o,
})

describe('openingCard', () => {
  it('shows what has been practised as a count out of the total, never a bare number', () => {
    const c = openingCard(row())
    expect(c.title).toBe('Caro-Kann Defence')
    expect(c.side).toBe('You play Black')
    expect(c.progress).toBe('12 of 80 positions practised')
    expect(c.accuracy).toBe('30 of 40 answers right')
    expect(c.canStart).toBe(true)
  })

  it('shows no accuracy before the first answer', () => {
    expect(openingCard(row({ hits: 0, misses: 0, nodes_seen: 0 })).accuracy).toBeNull()
  })

  it('says the book is missing, and cannot be started, when it has not been built', () => {
    const c = openingCard({ key: 'kings_indian', name: "King's Indian Defence", side: 'black', available: false })
    expect(c.canStart).toBe(false)
    expect(c.note).toBe('No book built yet. Run the line builder first.')
  })

  it('warns when the moves have not been checked by the engine', () => {
    expect(openingCard(row({ unchecked: true })).note).toBe('Moves are not engine-checked yet.')
  })

  it('says "line ends" for a single line', () => {
    expect(openingCard(row({ stopped: 1 })).note).toBe('1 line ends early where no common move passed the engine check.')
  })

  it('mentions lines that stopped because no played move passed the engine check', () => {
    expect(openingCard(row({ stopped: 2 })).note).toBe('2 lines end early where no common move passed the engine check.')
  })
})

describe('historyText', () => {
  it('writes the moves so far with move numbers', () => {
    expect(historyText(['e4', 'c6', 'd4'])).toBe('1. e4 c6 2. d4')
  })

  it('says it is the first move when nothing has been played', () => {
    expect(historyText([])).toBe('No moves yet. You play the first move.')
  })
})

describe('answerBanner', () => {
  it('names the move when it is right', () => {
    expect(answerBanner({ matched: true, expected_san: 'c6', your_san: 'c6' })).toEqual({ tone: 'right', text: 'Right: c6.' })
  })

  it('names both moves when it is wrong and says the line goes on', () => {
    expect(answerBanner({ matched: false, expected_san: 'c6', your_san: 'e5' })).toEqual({
      tone: 'wrong',
      text: 'You played e5. The line plays c6. It will come back sooner.',
    })
  })
})

describe('summaryText', () => {
  it('gives the answers as a count out of the total', () => {
    expect(summaryText({ answered: 6, hits: 5, misses: 1 })).toBe('5 of 6 right. 1 will come back sooner.')
  })

  it('has nothing to say about misses when there were none', () => {
    expect(summaryText({ answered: 4, hits: 4, misses: 0 })).toBe('4 of 4 right.')
  })
})

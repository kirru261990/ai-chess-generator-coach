import { describe, expect, it } from 'vitest'
import { answerBanner, arrowFor, historyText, openingCard, sourceLabel, summaryText, type Answer, type Question, type OpeningRow } from './repertoireState'

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
  nodes_engine: 0,
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

  it('says how many positions are the engine choice, so they are not mistaken for what players play', () => {
    expect(openingCard(row({ nodes_engine: 30 })).engineNote).toBe("30 of those positions are the engine's choice where players' games run out.")
    expect(openingCard(row()).engineNote).toBeNull()
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
    expect(answerBanner({ matched: true, expected_san: 'c6' })).toEqual({ tone: 'right', text: 'Right: c6.' })
  })

  it('says it is not the line and to try again, without naming the move, on a first wrong try', () => {
    expect(answerBanner({ matched: false, expected_san: null })).toEqual({ tone: 'wrong', text: "Not the line's move. Try again." })
  })

  it('names the move and points at the arrow once it is revealed', () => {
    expect(answerBanner({ matched: false, expected_san: 'c6' })).toEqual({
      tone: 'wrong',
      text: "Not the line's move. The line plays c6: follow the arrow.",
    })
  })
})

describe('summaryText', () => {
  it('says how many were right first time out of those asked', () => {
    expect(summaryText({ answered: 6, hits: 5, misses: 1, shown: 0 })).toBe('5 of 6 right first time. 1 will come back sooner.')
  })

  it('has nothing to say about misses when there were none', () => {
    expect(summaryText({ answered: 4, hits: 4, misses: 0, shown: 0 })).toBe('4 of 4 right first time.')
  })

  it('does not call an arrow-guided run right or wrong', () => {
    expect(summaryText({ answered: 6, hits: 0, misses: 0, shown: 6 })).toBe('You played all 6 moves with the arrow.')
  })
})

describe('arrowFor', () => {
  const q = (arrow: string | null) => ({ arrow }) as Question
  const a = (o: Partial<Answer>) => ({ retry: true, expected_uci: null, ...o }) as Answer

  it('draws the arrow of a learn run from the start', () => {
    expect(arrowFor(q('c7c6'), null)).toEqual([{ startSquare: 'c7', endSquare: 'c6', color: 'rgba(80, 140, 230, 0.85)' }])
  })

  it('draws nothing in a recall run until the move is revealed', () => {
    expect(arrowFor(q(null), null)).toEqual([])
    expect(arrowFor(q(null), a({ expected_uci: null }))).toEqual([])
  })

  it('draws the revealed move after repeated wrong tries', () => {
    expect(arrowFor(q(null), a({ expected_uci: 'c7c6' }))).toHaveLength(1)
  })
})

describe('sourceLabel', () => {
  it('labels an engine position and says nothing for a players position', () => {
    expect(sourceLabel('engine')).toBe("Engine line: the engine's choice here, not what most players at this level play.")
    expect(sourceLabel('players')).toBeNull()
  })
})

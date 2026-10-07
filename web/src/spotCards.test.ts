import { describe, expect, it } from 'vitest'
import { badge, cards, engineText, type TimeControlResult } from './spotCards'

const tc: TimeControlResult = {
  games: 50,
  user_moves: 1632,
  detectors: {
    hanging_own: {
      version: '2',
      counts: { taken: 1215, missed: 60, uncertain: 69, not_applicable: 288 },
      games_with_a_miss: 35,
      opportunities: 1275,
      moves_counted: 1563,
      missed_per_100_moves: { k: 60, n: 1563, rate: 3.84, ci95: [3.0, 4.9] },
      label: 'established',
    },
    missed_free: {
      version: '2',
      counts: { taken: 173, missed: 19, uncertain: 25, not_applicable: 1415 },
      games_with_a_miss: 13,
      opportunities: 192,
      moves_counted: 1607,
      missed_per_100_moves: { k: 19, n: 1607, rate: 1.18, ci95: [0.8, 1.8] },
      missed_of_available: { k: 19, n: 192, rate: 0.099, ci95: [0.06, 0.15] },
      label: 'established',
    },
  },
}

describe('cards', () => {
  it('shows missed free pieces as missed out of available, never a bare count', () => {
    const c = cards(tc).find((x) => x.key === 'missed_free')!
    expect(c.headline).toBe('You missed it 19 of 192 times (10%)')
    expect(c.range).toBe('Likely between 6% and 15%')
    expect(c.facts).toContain('Happened in 13 of your 50 games')
    expect(c.facts).toContain('25 moves were too unclear to judge, so they are left out')
  })

  it('shows hanging pieces per 100 moves with the move count', () => {
    const c = cards(tc).find((x) => x.key === 'hanging_own')!
    expect(c.headline).toBe('About 3.8 times in every 100 of your moves (60 times in 1563 moves)')
  })

  it('says so when there is nothing to measure', () => {
    const empty = structuredClone(tc)
    empty.detectors.missed_free.missed_of_available = null
    expect(cards(empty)[0].headline).toBe('No free pieces came up to measure')
  })
})

describe('labels and engine text', () => {
  it('uses plain words for the confidence labels', () => {
    expect(badge('established')).toBe('Solid sample')
    expect(badge('tentative')).toBe('Early sign')
    expect(badge('insufficient')).toBe('Not enough data yet')
  })

  it('reads both the old and the new engine layout', () => {
    expect(engineText([{ engine: 'Stockfish 19', depth: 10 }])).toBe('Stockfish 19, depth 10')
    expect(engineText({ name: 'Stockfish 19', budget: { depth: 10 } })).toBe(
      'Stockfish 19, depth 10',
    )
  })
})

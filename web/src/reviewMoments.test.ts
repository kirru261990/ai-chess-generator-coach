import { describe, expect, it } from 'vitest'
import { gameLabel, intentMessage, type IntentResult } from './reviewMoments'

const base: IntentResult = { ply: 4, answer: 'x', status: 'compared', spotted: [], gaps: [], facts: [] }

describe('intentMessage', () => {
  it('says nothing when the question was skipped', () => {
    expect(intentMessage({ ...base, status: 'skipped' })).toEqual([])
  })

  it('separates what the player saw from what they did not mention', () => {
    const m = intentMessage({ ...base, spotted: ['A'], gaps: ['B'] })
    expect(m).toEqual(['You saw: A', 'You did not mention:', 'B'])
  })

  it('lists the facts instead when the coach could not compare', () => {
    const m = intentMessage({ ...base, status: 'unavailable', facts: [{ id: 1, text: 'Fact one' }] })
    expect(m[m.length - 1]).toBe('Fact one')
  })

  it('does not claim anything when nothing matched', () => {
    expect(intentMessage(base)).toEqual(['Nothing on my list matched your answer.'])
  })
})

describe('gameLabel', () => {
  it('shows the time control by its plain name', () => {
    const label = gameLabel({
      game_id: '1', opponent: 'bob', user_color: 'white', user_result: 'win',
      time_control: '900+10', end_time: 1_791_000_000, analysed: true,
    })
    expect(label).toContain('15|10')
    expect(label).toContain('vs bob')
  })
})

import { describe, expect, it } from 'vitest'
import {
  feedbackMarks, hintButton, hintMarks, practiceLabel, stepTitle, summaryLines,
  type Hint, type PracticeFeedback, type PracticeStatus, type PracticeSummary,
} from './practiceState'

const fen = '4k3/8/8/8/8/2b5/8/R5K1 w - - 0 1'

describe('hintMarks', () => {
  const hints: Hint[] = [
    { level: 1, kind: 'last_move', text: 'x', squares: ['c8', 'c3'] },
    { level: 2, kind: 'piece', text: 'y', squares: ['a1'] },
    { level: 3, kind: 'line', text: 'z', uci: ['c3a1'], san: ['Bxa1'] },
  ]
  it('shows only what was asked for', () => {
    expect(hintMarks([])).toEqual({ squares: {}, arrows: [] })
    expect(Object.keys(hintMarks(hints.slice(0, 1)).squares)).toEqual(['c8', 'c3'])
    const all = hintMarks(hints)
    expect(all.squares.a1).toBeTruthy()
    expect(all.arrows).toHaveLength(1)
    expect(all.arrows[0]).toMatchObject({ startSquare: 'c3', endSquare: 'a1' })
  })
})

describe('feedbackMarks', () => {
  const fb = {
    target_squares: ['a1'], board_line: ['g1g2', 'c3a1'],
  } as PracticeFeedback
  it('marks your piece in danger red and draws the line', () => {
    const m = feedbackMarks(fb, fen, 'white')
    expect(m.squares.a1).toContain('220, 60, 50')
    expect(m.arrows.map((a) => a.startSquare + a.endSquare)).toEqual(['g1g2', 'c3a1'])
  })
  it('marks their piece green', () => {
    const m = feedbackMarks({ ...fb, target_squares: ['c3'] }, fen, 'white')
    expect(m.squares.c3).toContain('60, 170, 90')
  })
})

describe('words', () => {
  it('has a step title per stage and type', () => {
    expect(stepTitle('recognition', 'M1')).toContain('YOUR pieces')
    expect(stepTitle('recognition', 'M2')).toContain('THEIR pieces')
    expect(stepTitle('move', 'M1')).toContain('castle')
    expect(stepTitle('feedback', 'M1')).toBe('3. Feedback')
  })
  it('offers the next hint until all three are used', () => {
    expect(hintButton(0)).toBe('Give me a hint')
    expect(hintButton(2)).toContain('2 of 3')
    expect(hintButton(3)).toBeNull()
  })
  it('summarises a session without calling it a score', () => {
    const s = { completed: 5, total: 5, first_attempt_correct: 3, assisted_correct: 1, needed_retry: 1, recognized: 2 } as PracticeSummary
    expect(summaryLines(s)).toEqual([
      'Positions completed: 5 of 5', 'Right on the first try with no hint: 3', 'Right on the first try with a hint: 1',
      'Needed another try: 1', 'Spotted the problem yourself, with no hint: 2',
    ])
  })
})

describe('practiceLabel', () => {
  const base: PracticeStatus = { unlocked: true, positions: { unseen: 10, to_repeat: 2 }, session: null, last_completed: null }
  it('locks until the starting test, resumes, starts, and blocks a tiny pool', () => {
    expect(practiceLabel({ ...base, unlocked: false }).button).toBeNull()
    expect(practiceLabel({ ...base, session: { session_id: 1, done: 2, total: 5 } }).button).toContain('2 of 5')
    expect(practiceLabel(base).button).toBe('Start practice')
    expect(practiceLabel({ ...base, positions: { unseen: 1, to_repeat: 1 } }).button).toBeNull()
  })
})

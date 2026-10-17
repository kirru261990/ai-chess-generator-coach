import { describe, expect, it } from 'vitest'
import {
  feedbackLanes, feedbackMarks, hintButton, hintMarks, practiceLabel, squareCentre, stepTitle, summaryLines,
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

describe('feedbackLanes', () => {
  const fb = {
    game_move: { uci: 'g1g2', san: 'Kg2' },
    board_line: ['g1g2', 'c3a1', 'h1h2', 'a1b2', 'x'], board_line_san: ['Kg2', 'Bxa1', 'Rh2', 'Bb2', 'x'],
    your_move: { uci: 'a1a8', san: 'Ra8+' }, sound: false,
    good_moves: [{ uci: 'a1b1', san: 'Rb1' }, { uci: 'a1c1', san: 'Rc1' }],
  } as PracticeFeedback
  const row = (l: ReturnType<typeof feedbackLanes>, s: string) => l.filter((x) => x.series === s).map((x) => [x.n, x.who, x.san])
  it('numbers each series from 1 on its own', () => {
    const l = feedbackLanes(fb, 'M1')
    expect(row(l, 'game')).toEqual([[1, 'You', 'Kg2'], [2, 'Opponent', 'Bxa1'], [3, 'You', 'Rh2'], [4, 'Opponent', 'Bb2']])
    expect(row(l, 'now')).toEqual([[1, 'You', 'Ra8+']])
    expect(row(l, 'best')).toEqual([[1, 'You', 'Rb1'], [2, 'You', 'Rc1']])
  })
  it('draws no arrows for a sound move except the game line on request', () => {
    const l = feedbackLanes({ ...fb, sound: true }, 'M1')
    expect(l.every((x) => x.series === 'game')).toBe(true)
  })
  it('marks an unsound move as such', () => {
    expect(feedbackLanes(fb, 'M1').find((x) => x.series === 'now')?.notSound).toBe(true)
  })
  it('for free pieces: your game move in red, the capture line in green when the move was not sound', () => {
    const l = feedbackLanes({ ...fb, board_line: ['c3a1', 'b2a1'], board_line_san: ['Bxa1', 'Kxa1'] }, 'M2')
    expect(row(l, 'game')).toEqual([[1, 'You', 'Kg2']])
    expect(row(l, 'best')).toEqual([[1, 'You', 'Bxa1'], [2, 'Opponent', 'Kxa1']])
  })
})

describe('squareCentre', () => {
  it('flips for black', () => {
    expect(squareCentre('a1', 'white')).toEqual({ x: 0.5, y: 7.5 })
    expect(squareCentre('a1', 'black')).toEqual({ x: 7.5, y: 0.5 })
  })
})

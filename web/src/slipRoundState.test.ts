import { describe, expect, it } from 'vitest'
import { answerLine, clampStep, pointsTag, reviewFrame, roundLine, timerState, TIMER_CHOICES, type Review } from './slipRoundState'

const review: Review = {
  start_fen: 'start',
  mine: [
    { uci: 'd2d5', san: 'Qxd5', who: 'you', points: 1, fen: 'a' },
    { uci: 'c6d5', san: 'cxd5', who: 'they', points: -8, fen: 'b' },
    { uci: 'e1f1', san: 'Kf1', who: 'you', points: -8, fen: 'c' },
  ],
  better: [{ uci: 'e1f1', san: 'Kf1', who: 'you', points: 0, fen: 'd' }],
}

describe('timerState', () => {
  it('counts down, turns low at 3 seconds and says over time at the limit', () => {
    expect(timerState(15, 0)).toMatchObject({ label: '15 s', fraction: 1, level: 'ok' })
    expect(timerState(15, 6_200)).toMatchObject({ label: '9 s', level: 'ok' })
    expect(timerState(15, 12_100)).toMatchObject({ label: '3 s', level: 'low' })
    expect(timerState(15, 15_000)).toMatchObject({ label: 'Over time', fraction: 0, level: 'over' })
    expect(timerState(8, 99_000)).toMatchObject({ label: 'Over time', fraction: 0 })
  })
  it('has no countdown without a timer', () => {
    expect(timerState(0, 99_000)).toMatchObject({ label: 'No timer', level: 'none' })
  })
})

describe('timer choices', () => {
  it('offers 15 seconds first (the default), then 8, then none', () => {
    expect(TIMER_CHOICES.map((c) => c.seconds)).toEqual([15, 8, 0])
    expect(TIMER_CHOICES[0].hint).toContain('10-minute')
  })
})

describe('pointsTag', () => {
  it('says level, or your gain or loss with a real minus sign and the singular for one point', () => {
    expect(pointsTag(0)).toBe('Level')
    expect(pointsTag(-8)).toBe('You −8 points')
    expect(pointsTag(1)).toBe('You +1 point')
    expect(pointsTag(3)).toBe('You +3 points')
  })
})

describe('reviewFrame', () => {
  it('starts on the start position with no arrows', () => {
    expect(reviewFrame(review, 'mine', 0)).toEqual({ fen: 'start', arrows: [], caption: 'Start', points: null, step: 0, last: 3 })
  })
  it('shows the position after the step, the latest move bold and earlier moves faded, coloured by who moves', () => {
    const f = reviewFrame(review, 'mine', 2)
    expect(f.fen).toBe('b')
    expect(f.caption).toBe('They: cxd5')
    expect(f.points).toBe('You −8 points')
    expect(f.arrows).toEqual([
      { startSquare: 'd2', endSquare: 'd5', color: 'rgba(217, 83, 79, 0.3)' },
      { startSquare: 'c6', endSquare: 'd5', color: 'rgba(240, 173, 78, 0.8)' },
    ])
  })
  it('colours your moves green in the better line', () => {
    expect(reviewFrame(review, 'better', 1).arrows[0].color).toBe('rgba(60, 154, 95, 0.8)')
  })
})

describe('clampStep', () => {
  it('stays inside the line', () => {
    expect(clampStep(review, 'mine', -1)).toBe(0)
    expect(clampStep(review, 'mine', 9)).toBe(3)
    expect(clampStep(review, 'better', 5)).toBe(1)
  })
})

describe('answerLine', () => {
  it('says matched or not matched without calling a move wrong, with time and over time', () => {
    expect(answerLine({ matched: true, your_move: 'e4', elapsed_ms: 6_000, over_time: false })).toBe('Yes, e4 is one of the checked moves. 6 s.')
    expect(answerLine({ matched: false, your_move: 'a3', elapsed_ms: 21_000, over_time: true })).toBe('a3 is not one of the checked moves. 21 s, over time.')
  })
})

describe('roundLine', () => {
  it('keeps the denominators', () => {
    expect(roundLine({ answered: 10, total: 10, matched: 6, over_time: 2, median_ms: 9_400 })).toBe('6 of 10 matched · 2 of 10 over time · middle time 9 s')
  })
})

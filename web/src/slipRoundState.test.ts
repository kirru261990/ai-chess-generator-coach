import { describe, expect, it } from 'vitest'
import { answerLine, boardMarks, clampStep, keyStep, promotionChoices, tickMs, pointsTag, reviewFrame, roundLine, timerState, TIMER_CHOICES, type Review } from './slipRoundState'

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
    expect(answerLine({ matched: true, your_move: 'e4', elapsed_ms: 6_000, over_time: false })).toBe('e4 matched · 6 s')
    expect(answerLine({ matched: false, your_move: 'a3', elapsed_ms: 21_000, over_time: true })).toBe('a3 not matched · 21 s · over time')
  })
})

describe('roundLine', () => {
  it('keeps the denominators', () => {
    expect(roundLine({ answered: 10, total: 10, matched: 6, over_time: 2, median_ms: 9_400 })).toBe('6 of 10 matched · 2 of 10 over time · middle time 9 s')
  })
})


describe('boardMarks', () => {
  const answered = { uci: 'e2e4', matched: true }
  it('marks your answer with a blue arrow, and a star when it matched, on the start position', () => {
    const m = boardMarks(reviewFrame(review, 'mine', 0), 'mine', answered)
    expect(m.arrows).toEqual([{ startSquare: 'e2', endSquare: 'e4', color: 'rgba(80, 140, 230, 0.85)' }])
    expect(m.badge).toMatchObject({ square: 'e4', symbol: '★', tone: 'best' })
  })
  it('does not call a miss wrong: a blue arrow and no badge', () => {
    const m = boardMarks(reviewFrame(review, 'mine', 0), 'mine', { uci: 'a2a3', matched: false })
    expect(m.arrows).toHaveLength(1)
    expect(m.badge).toBeNull()
  })
  it('labels the first move of each line on the moved piece: the game move with a question mark, the better move with a star', () => {
    expect(boardMarks(reviewFrame(review, 'mine', 1), 'mine', answered).badge).toMatchObject({ square: 'd5', symbol: '?', tone: 'mistake', label: 'The move you played in the game' })
    expect(boardMarks(reviewFrame(review, 'better', 1), 'better', answered).badge).toMatchObject({ square: 'f1', symbol: '★', tone: 'best', label: 'The better move' })
  })
  it('puts no badge on later moves, only the fading arrows', () => {
    const f = reviewFrame(review, 'mine', 2)
    expect(boardMarks(f, 'mine', answered)).toEqual({ arrows: f.arrows, badge: null, squares: [], text: null })
  })
})

describe('boardMarks with the why', () => {
  const answered = { uci: 'e2e4', matched: true }
  const why = {
    mine: { step: 1, text: 'Your queen on d1 can be taken by their bishop.', arrows: [{ from: 'g4', to: 'd1', tone: 'their' as const }], squares: ['d1'] },
    better: { step: 0, text: 'You could win their rook on d5 with your queen.', arrows: [{ from: 'd2', to: 'd5', tone: 'better' as const }], squares: ['d5'] },
  }
  it('adds the sentence, an orange arrow for their move and a ring on the square, only at the step the why belongs to', () => {
    const m = boardMarks(reviewFrame(review, 'mine', 1), 'mine', answered, why)
    expect(m.text).toBe('Your queen on d1 can be taken by their bishop.')
    expect(m.squares).toEqual(['d1'])
    expect(m.arrows.at(-1)).toEqual({ startSquare: 'g4', endSquare: 'd1', color: 'rgba(240, 173, 78, 0.8)' })
    const later = boardMarks(reviewFrame(review, 'mine', 2), 'mine', answered, why)
    expect(later.text).toBeNull()
    expect(later.squares).toEqual([])
  })
  it('draws a capture you could make in green, and says nothing when there is no why for that line', () => {
    const m = boardMarks(reviewFrame(review, 'better', 0), 'better', answered, why)
    expect(m.arrows.at(-1)).toEqual({ startSquare: 'd2', endSquare: 'd5', color: 'rgba(60, 154, 95, 0.8)' })
    expect(boardMarks(reviewFrame(review, 'better', 1), 'better', answered, { mine: null, better: null }).text).toBeNull()
    expect(boardMarks(reviewFrame(review, 'better', 1), 'better', answered, null).text).toBeNull()
  })
})


describe('keyStep', () => {
  it('steps the line with the arrow keys and ignores everything else', () => {
    expect(keyStep('ArrowRight')).toBe(1)
    expect(keyStep('ArrowLeft')).toBe(-1)
    expect(keyStep('Enter')).toBe(0)
  })
})

describe('tickMs', () => {
  it('updates the countdown four times a second, or once a second when the viewer prefers reduced motion', () => {
    expect(tickMs(false)).toBe(250)
    expect(tickMs(true)).toBe(1000)
  })
})


describe('promotionChoices', () => {
  const legal = ['c7c8q', 'c7c8r', 'c7c8b', 'c7c8n', 'c7b8q', 'a1a2']
  it('offers the four pieces when a pawn reaches the last rank, so the player chooses', () => {
    expect(promotionChoices(legal, 'c7', 'c8')).toEqual([
      { uci: 'c7c8q', label: 'Queen' }, { uci: 'c7c8r', label: 'Rook' }, { uci: 'c7c8b', label: 'Bishop' }, { uci: 'c7c8n', label: 'Knight' },
    ])
  })
  it('offers nothing for an ordinary move', () => {
    expect(promotionChoices(legal, 'a1', 'a2')).toEqual([])
    expect(promotionChoices(legal, 'h1', 'h2')).toEqual([])
  })
})

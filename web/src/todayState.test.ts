import { describe, expect, it } from 'vitest'
import type { HomeType } from './assessState'
import { rankFill, todayStep } from './todayState'

function home(over: Partial<HomeType> = {}): HomeType {
  return {
    mistake_type: 'M1',
    label: 'Pieces left in danger',
    pool: { mistake_positions: 35, clean_positions: 74, needed_mistake_positions: 16, needed_clean_positions: 8, ready: true },
    baseline: { assessment_id: 3, status: 'submitted' },
    delayed: { waiting: null, done: [] },
    practice: { unlocked: true, positions: { unseen: 0, to_repeat: 0 }, session: null, last_completed: null },
    ...over,
  }
}

describe('todayStep', () => {
  it('finishes a half-done starting test first', () => {
    const t = todayStep([
      home({ delayed: { waiting: { assessment_id: 4, status: 'pending', due_at: '', available: true }, done: [] } }),
      home({ mistake_type: 'M2', label: 'Free pieces to take', baseline: { assessment_id: 2, status: 'in_progress' } }),
    ])
    expect(t.action).toEqual({ kind: 'test', id: 2 })
    expect(t.text).toContain('Free pieces to take')
  })

  it('puts an open delayed test before practice', () => {
    const t = todayStep([
      home({ practice: { unlocked: true, positions: { unseen: 33, to_repeat: 5 }, session: { session_id: 9, done: 2, total: 10 }, last_completed: null } }),
      home({ mistake_type: 'M2', delayed: { waiting: { assessment_id: 4, status: 'pending', due_at: '', available: true }, done: [] } }),
    ])
    expect(t).toMatchObject({ button: 'Take the test', action: { kind: 'test', id: 4 } })
  })

  it('ignores a delayed test that is not open yet', () => {
    const t = todayStep([home({ delayed: { waiting: { assessment_id: 4, status: 'pending', due_at: '', available: false }, done: [] } })])
    expect(t.action.kind).toBe('play')
  })

  it('resumes practice before starting anything new', () => {
    const t = todayStep([
      home({ mistake_type: 'M2', baseline: null }),
      home({ practice: { unlocked: true, positions: { unseen: 3, to_repeat: 0 }, session: { session_id: 9, done: 2, total: 10 }, last_completed: null } }),
    ])
    expect(t).toMatchObject({ text: 'Practice on “Pieces left in danger”: 2 of 10 done', action: { kind: 'practice', id: 9 } })
  })

  it('starts a test only when the pool is ready', () => {
    const notReady = home({ baseline: null, pool: { mistake_positions: 3, clean_positions: 4, needed_mistake_positions: 16, needed_clean_positions: 8, ready: false } })
    expect(todayStep([notReady]).action.kind).toBe('play')
    expect(todayStep([home({ baseline: null })]).action).toEqual({ kind: 'start-test', mistakeType: 'M1' })
  })

  it('offers practice only with at least 3 positions left', () => {
    const few = home({ practice: { unlocked: true, positions: { unseen: 1, to_repeat: 1 }, session: null, last_completed: null } })
    expect(todayStep([few]).action.kind).toBe('play')
    const t = todayStep([home({ practice: { unlocked: true, positions: { unseen: 33, to_repeat: 5 }, session: null, last_completed: 1 } })])
    expect(t).toMatchObject({ text: '38 positions from your games to practise for “Pieces left in danger”', action: { kind: 'start-practice', mistakeType: 'M1' } })
  })
})

describe('rankFill', () => {
  it('rounds to eighths', () => {
    expect(rankFill(78, 134)).toBe(5)
    expect(rankFill(1, 2)).toBe(4)
  })
  it('keeps 0 and 1 apart from near misses', () => {
    expect(rankFill(0, 50)).toBe(0)
    expect(rankFill(1, 100)).toBe(1)
    expect(rankFill(99, 100)).toBe(7)
    expect(rankFill(5, 5)).toBe(8)
    expect(rankFill(3, 0)).toBe(0)
  })
})

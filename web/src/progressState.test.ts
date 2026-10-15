import { describe, expect, it } from 'vitest'
import {
  comparisonLines, delayedLabel, delayedSummaryLine, dueText, practiceLines, testLines,
  type Comparison, type PracticeStats, type TestSummary,
} from './progressState'

const NOW = Date.parse('2026-10-15T12:00:00Z')
const h = (n: number) => new Date(NOW + n * 3_600_000).toISOString()

describe('dueText', () => {
  it('says open now, or when and in how many hours', () => {
    expect(dueText(h(-1), NOW)).toBe('Open now')
    expect(dueText(h(0), NOW)).toBe('Open now')
    expect(dueText(h(72), NOW)).toContain('in about 72 hours')
    expect(dueText(h(0.2), NOW)).toContain('in about 1 hour)')
    expect(dueText('garbage', NOW)).toBe('Open now')
  })
})

describe('delayedLabel', () => {
  it('shows nothing, a waiting test, an open test, and how many are done', () => {
    expect(delayedLabel({ waiting: null, done: [] }, NOW)).toEqual({ note: null, takeId: null })
    expect(delayedLabel({ waiting: null, done: [4, 7] }, NOW)).toEqual({ note: 'Delayed tests done: 2.', takeId: null })
    const closed = delayedLabel({ waiting: { assessment_id: 9, status: 'pending', due_at: h(30), available: false }, done: [] }, NOW)
    expect(closed.takeId).toBeNull()
    expect(closed.note).toContain('in about 30 hours')
    const open = delayedLabel({ waiting: { assessment_id: 9, status: 'pending', due_at: h(-1), available: true }, done: [4] }, NOW)
    expect(open.takeId).toBe(9)
    expect(open.note).toContain('is open')
  })
})

describe('delayedSummaryLine', () => {
  it('covers the three cases', () => {
    expect(delayedSummaryLine({ status: 'scheduled', assessment_id: 1, due_at: h(72) }, NOW)).toContain('delayed test is set')
    expect(delayedSummaryLine({ status: 'pending_exists', assessment_id: 1, due_at: h(10) }, NOW)).toContain('already waiting')
    expect(delayedSummaryLine({ status: 'no_positions' }, NOW)).toContain('No unused positions')
  })
})

const test: TestSummary = {
  assessment_id: 1, kind: 'BASELINE', question_version: '2', total: 4, left_out_count: 1,
  scores: { recognition: 3, move: 1, combined: 1 }, chance: { recognition: 0.4, move: 0.9, combined: null },
  chance_pending: true, mean_seconds: 50, timed: 4, interrupted: 0,
}

describe('testLines', () => {
  it('puts every score next to its guessing level and notes left-out and version 1', () => {
    const lines = testLines(test)
    expect(lines[0]).toBe('Played a sound move: 1 of 4 (guessing would get about 0.9)')
    expect(lines[2]).toContain('guessing: still calculating')
    expect(lines.join(' ')).toContain('1 position(s) left out')
    expect(lines.join(' ')).toContain('Average time per position: 50 s (4 timed)')
    expect(testLines({ ...test, question_version: '1' }).join(' ')).toContain('not comparable')
  })
})

describe('comparisonLines', () => {
  const c: Comparison = {
    baseline: { move: 0.25, total: 4 },
    delayed: [{ assessment_id: 2, total: 5, move: 0.6, recognition: 0.6, combined: 0.4 }],
    comparable: { move: true, recognition: true }, gain_move_positions_of_5: 1.8, gain_combined_positions_of_5: 1.1,
  }
  it('shows the change in positions out of 5 and the small-sample warning', () => {
    const lines = comparisonLines(c)
    expect(lines[0]).toBe('Sound move: starting test 25%; delayed test 1 60%.')
    expect(lines.join(' ')).toContain('+1.8 positions out of 5')
    expect(lines.join(' ')).toContain('+1.1 positions out of 5')
    expect(lines[lines.length - 1]).toContain('small sample')
  })
  it('does not compare the tap score across wordings', () => {
    const lines = comparisonLines({ ...c, comparable: { move: true, recognition: false }, gain_combined_positions_of_5: undefined })
    expect(lines.join(' ')).toContain('not compared')
    expect(lines.join(' ')).not.toContain('"both right": +')
  })
})

describe('practiceLines', () => {
  const p: PracticeStats = {
    assisted: true, sessions: 1, positions: 5, first_attempts: 5, first_attempt_correct: 0, assisted_correct: 1, recognized: 2,
    attempts: 9, retries: 4, attempts_with_hint: 1, mean_first_seconds: 64, not_sound: 7,
    reasons: [{ reason: 'a stronger move existed', count: 4 }],
  }
  it('has denominators and the reasons', () => {
    const text = practiceLines(p).join(' ')
    expect(text).toContain('right with no hint: 0 of 5')
    expect(text).toContain('Hints used on 1 of 9 tries')
    expect(text).toContain('a stronger move existed (4)')
    expect(practiceLines({ ...p, sessions: 0, attempts: 0 })).toEqual(['No practice yet.'])
  })
})

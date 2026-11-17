/**
 * The one next step for the Today strip, chosen from the coach home (`/coach/home`). Pure, so the order of priority is
 * tested; the server still owns whether a test or practice may start.
 */

import type { HomeType } from './assessState'

export type TodayAction =
  | { kind: 'test'; id: number } // open a test that already exists (a starting test half done, or a delayed test that is open)
  | { kind: 'practice'; id: number } // resume a practice session
  | { kind: 'start-test'; mistakeType: HomeType['mistake_type'] }
  | { kind: 'start-practice'; mistakeType: HomeType['mistake_type'] }
  | { kind: 'play' }

export type Today = { text: string; button: string; action: TodayAction }

const MIN_PRACTICE_POSITIONS = 3 // as practiceLabel: fewer than 3 left is not a session

/**
 * Finish what is started before starting anything new: a half-done starting test, then an open delayed test (it measures
 * whether practice helped, so it comes before more practice), then a practice session in progress, then a new starting
 * test, then new practice. With nothing to do, play a game.
 */
export function todayStep(types: HomeType[]): Today {
  const named = (t: HomeType) => `“${t.label}”`
  for (const t of types) {
    if (t.baseline && t.baseline.status !== 'submitted') {
      return { text: `Finish your starting test for ${named(t)}`, button: 'Continue the test', action: { kind: 'test', id: t.baseline.assessment_id } }
    }
  }
  for (const t of types) {
    if (t.delayed.waiting?.available) {
      return { text: `Your delayed test for ${named(t)} is open`, button: 'Take the test', action: { kind: 'test', id: t.delayed.waiting.assessment_id } }
    }
  }
  for (const t of types) {
    const s = t.practice.session
    if (s) {
      return { text: `Practice on ${named(t)}: ${s.done} of ${s.total} done`, button: 'Continue practice', action: { kind: 'practice', id: s.session_id } }
    }
  }
  for (const t of types) {
    if (!t.baseline && t.pool.ready) {
      return { text: `Take a 5-position starting test for ${named(t)}`, button: 'Start the test', action: { kind: 'start-test', mistakeType: t.mistake_type } }
    }
  }
  for (const t of types) {
    const left = t.practice.positions.unseen + t.practice.positions.to_repeat
    if (t.practice.unlocked && left >= MIN_PRACTICE_POSITIONS) {
      return { text: `${left} positions from your games to practise for ${named(t)}`, button: 'Start practice', action: { kind: 'start-practice', mistakeType: t.mistake_type } }
    }
  }
  return { text: 'Nothing waiting. Play a game', button: 'Play', action: { kind: 'play' } }
}

/** How many of the eight squares a rate fills: rounded to the nearest eighth, but never empty above 0 or full below 1. */
export function rankFill(n: number, of: number): number {
  if (of <= 0 || n <= 0) return 0
  if (n >= of) return 8
  return Math.min(7, Math.max(1, Math.round((8 * n) / of)))
}

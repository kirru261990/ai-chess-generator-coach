import { describe, expect, it } from 'vitest'
import { toolBackend } from './practiceBackend'

describe('the practice page backend over chat tools', () => {
  it('sends the position it is showing with every step, so a stale widget is refused by the server', async () => {
    const calls: [string, Record<string, unknown>][] = []
    const view = { session_id: 7 }
    const b = toolBackend(async (name, args) => (calls.push([name, args]), { structured: { view, summary: null }, text: '' }))
    await b.post(7, 'recognition', { ord: 2, tap: 'g5' })
    await b.post(7, 'move', { ord: 2, move: 'g1f3' })
    await b.post(7, 'hint', { ord: 2 })
    await b.post(7, 'retry', { ord: 2 })
    await b.post(7, 'next', { ord: 2 })
    expect(calls.map(([n]) => n)).toEqual(['practice_answer', 'practice_move', 'practice_hint', 'practice_retry', 'practice_next'])
    for (const [, args] of calls) expect(args).toMatchObject({ session_id: 7, expected_ord: 2 })
  })
})

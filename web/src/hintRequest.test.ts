import { describe, expect, it } from 'vitest'
import { requestHint } from './hintRequest'

const answer = (status: number, body: unknown) =>
  (async () => new Response(typeof body === 'string' ? body : JSON.stringify(body), { status })) as typeof fetch

describe('requestHint', () => {
  it('returns the steps on success', async () => {
    const data = { revision: 2, level: 1, max_level: 5, steps: [{ level: 1, kind: 'scan', text: 'Look' }], hints_used: 1 }
    expect(await requestHint('http://x', 'g1', 1, answer(200, data))).toEqual({ ok: true, data })
  })

  it('turns a 4xx into a message with the server reason', async () => {
    const r = await requestHint('http://x', 'g1', 2, answer(409, { error: 'no_hint', message: 'not your turn' }))
    expect(r).toEqual({ ok: false, message: 'No hint this time: not your turn. Try again.' })
  })

  it('turns a 5xx without a JSON body into a message with the status', async () => {
    const r = await requestHint('http://x', 'g1', 2, answer(500, 'Internal Server Error'))
    expect(r).toEqual({ ok: false, message: 'No hint this time (error 500). Try again.' })
  })

  it('turns a network failure into a message instead of throwing', async () => {
    const down = (async () => {
      throw new TypeError('Failed to fetch')
    }) as typeof fetch
    const r = await requestHint('http://x', 'g1', 1, down)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.message).toMatch(/could not reach the server/i)
  })

  it('rejects a success answer it cannot read', async () => {
    expect((await requestHint('http://x', 'g1', 1, answer(200, 'oops'))).ok).toBe(false)
  })
})

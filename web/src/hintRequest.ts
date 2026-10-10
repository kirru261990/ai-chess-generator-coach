import type { HintStep } from './gameState'

export type HintResponse = { revision: number; level: number; max_level: number; steps: HintStep[]; hints_used: number }
export type HintResult = { ok: true; data: HintResponse } | { ok: false; message: string }

/** Ask the server for hint steps 1..level. Never throws: every failure becomes a message the hint panel can show
 * next to a retry, so a failed hint is never silent. */
export async function requestHint(
  api: string,
  gameId: string,
  level: number,
  fetcher: typeof fetch = fetch,
): Promise<HintResult> {
  let res: Response
  try {
    res = await fetcher(`${api}/games/${gameId}/hint?level=${level}`)
  } catch {
    return { ok: false, message: 'Could not reach the server for a hint. Check that it is running, then try again.' }
  }
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    // an empty or non-JSON body: fall through to the status message
  }
  if (!res.ok) {
    const said = (data as { message?: string } | null)?.message
    return { ok: false, message: `No hint this time${said ? `: ${said}` : ` (error ${res.status})`}. Try again.` }
  }
  const body = data as HintResponse | null
  if (!body || !Array.isArray(body.steps)) {
    return { ok: false, message: 'The hint answer was not readable. Try again.' }
  }
  return { ok: true, data: body }
}

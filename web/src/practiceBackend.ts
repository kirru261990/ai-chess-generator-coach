import { api } from './api'
import type { PracticeSummary, PracticeView } from './practiceState'

/** Where the Practice page gets its data. The web app talks to the REST API; the chat board (an MCP app) calls the practice tools. */
export type PracticeBackend = {
  get(id: number): Promise<PracticeView>
  /** One step: `recognition` {ord, tap}, `move` {ord, move}, `hint` / `retry` / `next` {ord}. Resolves to the new view. */
  post(id: number, path: string, body: Record<string, unknown>): Promise<PracticeView>
  summary(id: number): Promise<PracticeSummary>
}

export const restBackend: PracticeBackend = {
  get: (id) => api<PracticeView>(`/coach/practice/sessions/${id}`),
  post: (id, path, body) => api<PracticeView>(`/coach/practice/sessions/${id}/${path}`, body),
  summary: (id) => api<PracticeSummary>(`/coach/practice/sessions/${id}/summary`),
}

/** What a board-showing tool returns as structured data (see `practice_tools.payload`). */
export type BoardPayload = { view: PracticeView; summary: PracticeSummary | null }

export type ToolCaller = (name: string, args: Record<string, unknown>) => Promise<{ structured: unknown; text: string }>

/** The same page over the chat tools. A step becomes one tool call; its structured data is the new view. A refused step has only
 *  text, which becomes the error shown on the page. */
export function toolBackend(call: ToolCaller): PracticeBackend {
  const TOOL: Record<string, (id: number, b: Record<string, unknown>) => [string, Record<string, unknown>]> = {
    recognition: (id, b) => ['practice_answer', { session_id: id, square: b.tap, expected_ord: b.ord }],
    move: (id, b) => ['practice_move', { session_id: id, move: b.move, expected_ord: b.ord }],
    hint: (id, b) => ['practice_hint', { session_id: id, expected_ord: b.ord }],
    retry: (id, b) => ['practice_retry', { session_id: id, expected_ord: b.ord }],
    next: (id, b) => ['practice_next', { session_id: id, expected_ord: b.ord }],
  }
  const summaries = new Map<number, PracticeSummary>()
  const run = async (name: string, args: Record<string, unknown>): Promise<PracticeView> => {
    const { structured, text } = await call(name, args)
    const data = structured as BoardPayload | null
    if (!data?.view) throw new Error(text.replace(/^I could not do that: /, '') || 'that did not work')
    if (data.summary) summaries.set(data.view.session_id, data.summary)
    return data.view
  }
  return {
    get: (id) => run('practice_show', { session_id: id }),
    post: (id, path, body) => {
      const make = TOOL[path]
      if (!make) return Promise.reject(new Error(`unknown step ${path}`))
      const [name, args] = make(id, body)
      return run(name, args)
    },
    summary: async (id) => {
      const s = summaries.get(id)
      if (s) return s
      throw new Error('the summary is not available here yet')
    },
  }
}

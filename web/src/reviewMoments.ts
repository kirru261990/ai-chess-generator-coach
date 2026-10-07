// Types and small helpers for the Review tab. Text about the position comes from the backend; nothing is invented here.

export type SyncedGame = {
  game_id: string
  opponent: string
  user_color: 'white' | 'black'
  user_result: string
  time_control: string
  end_time: number
  analysed: boolean
}

export type Moment = {
  ply: number
  move_number: number
  fen_before: string
  played: { uci: string; san: string }
  best: { uci: string; san: string }
  takeaway: string
}

export type Review = {
  game_id: string
  user_color: 'white' | 'black'
  opponent: string
  result: string
  moments: Moment[]
}

export type IntentResult = {
  ply: number
  answer: string
  status: 'compared' | 'skipped' | 'nothing_to_compare' | 'unavailable'
  spotted: string[]
  gaps: string[]
  facts: { id: number; text: string }[]
}

export const TIME_CONTROL_LABEL: Record<string, string> = { '600': '10|0', '900+10': '15|10' }

export function gameLabel(g: SyncedGame): string {
  const when = new Date(g.end_time * 1000).toLocaleDateString()
  const tc = TIME_CONTROL_LABEL[g.time_control] ?? g.time_control
  return `${when} · ${tc} · vs ${g.opponent} · ${g.user_result}`
}

/** What to tell the player about their answer. Wording only; every fact in it was built by the backend. */
export function intentMessage(r: IntentResult): string[] {
  switch (r.status) {
    case 'skipped':
      return []
    case 'nothing_to_compare':
      return ['Nothing special was on the board here, so there is nothing to compare your answer with.']
    case 'unavailable':
      return [
        'I could not compare your answer right now. Here is what was on the board:',
        ...r.facts.map((f) => f.text),
      ]
    case 'compared': {
      const lines = r.spotted.map((t) => `You saw: ${t}`)
      if (r.gaps.length > 0) lines.push('You did not mention:', ...r.gaps)
      if (r.gaps.length === 0 && r.spotted.length > 0) lines.push('You noticed everything that mattered here.')
      if (r.gaps.length === 0 && r.spotted.length === 0) lines.push('Nothing on my list matched your answer.')
      return lines
    }
  }
}

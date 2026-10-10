// The evaluation bar. Numbers come from the engine (via the backend); this file only turns them into a bar and a label.

export type Evaluation = { revision: number; cp: number | null; mate: number | null; mate_sign: number | null; best_move?: string | null }

/** Share of the bar that belongs to White, 0..1. Logistic in centipawns; a mate fills the bar for the side that mates. */
export function whiteShare(e: Pick<Evaluation, 'cp' | 'mate' | 'mate_sign'>): number {
  if (e.mate !== null) {
    const sign = e.mate_sign ?? (e.mate > 0 ? 1 : -1)
    return sign > 0 ? 1 : 0
  }
  const cp = e.cp ?? 0
  return 1 / (1 + Math.pow(10, -cp / 400))
}

/** Short label for the bar: +1.4, -0.3, M3 (mate in 3). Positive favours White. */
export function evalLabel(e: Pick<Evaluation, 'cp' | 'mate' | 'mate_sign'>): string {
  if (e.mate !== null) {
    if (e.mate === 0) return e.mate_sign === 1 ? '1-0' : '0-1'
    return `M${Math.abs(e.mate)}`
  }
  const pawns = (e.cp ?? 0) / 100
  return `${pawns >= 0 ? '+' : '-'}${Math.abs(pawns).toFixed(1)}`
}

/** The same thing in words, for people who do not read numbers (and for screen readers). */
export function evalWords(e: Pick<Evaluation, 'cp' | 'mate' | 'mate_sign'>): string {
  if (e.mate !== null) {
    const who = (e.mate_sign ?? (e.mate > 0 ? 1 : -1)) > 0 ? 'White' : 'Black'
    return e.mate === 0 ? `${who} has won by checkmate` : `${who} can force checkmate in ${Math.abs(e.mate)}`
  }
  const cp = e.cp ?? 0
  const size = Math.abs(cp)
  if (size < 30) return 'The position is about equal'
  const who = cp > 0 ? 'White' : 'Black'
  if (size < 100) return `${who} is slightly better`
  if (size < 250) return `${who} is better`
  if (size < 500) return `${who} is much better`
  return `${who} is winning`
}

/** An evaluation belongs to one position: use it only for the game and revision it was computed for. */
export function evalIsCurrent(e: (Evaluation & { gameId: string }) | null, gameId: string, revision: number): boolean {
  return e !== null && e.gameId === gameId && e.revision === revision
}

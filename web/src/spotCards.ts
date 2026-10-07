// Turns the frozen baseline results into plain-words cards. Pure functions: no numbers are invented here,
// every figure shown is copied from the backend's results (rule 3: rates come with their denominators).

export type Rate = { k: number; n: number; rate: number; ci95: [number, number] }
export type DetectorResult = {
  version: string
  counts: { taken: number; missed: number; uncertain: number; not_applicable: number }
  games_with_a_miss: number
  opportunities: number
  moves_counted: number
  missed_per_100_moves: Rate | null
  missed_of_available?: Rate | null
  label: 'insufficient' | 'tentative' | 'established'
}
export type TimeControlResult = {
  games: number
  user_moves: number
  detectors: Record<string, DetectorResult>
}
export type BlindSpotsResponse = {
  results: {
    by_time_control: Record<string, TimeControlResult>
    engine: { name?: string; budget?: { depth: number } } | { engine: string; depth: number }[]
  }
  results_sha256: string
}

export type Card = {
  key: string
  title: string
  what: string
  headline: string
  range: string
  badge: string
  badgeKind: DetectorResult['label']
  facts: string[]
}

const per100 = (n: number) => n.toFixed(1)
const pct = (x: number) => `${Math.round(x * 100)}%`

export function engineText(engine: BlindSpotsResponse['results']['engine']): string {
  const first = Array.isArray(engine) ? engine[0] : engine
  const name = first && ('name' in first ? first.name : 'engine' in first ? first.engine : undefined)
  const depth = first && ('depth' in first ? first.depth : 'budget' in first ? first.budget?.depth : undefined)
  return `${name ?? 'the engine'}${depth ? `, depth ${depth}` : ''}`
}

export function badge(label: DetectorResult['label']): string {
  return { established: 'Solid sample', tentative: 'Early sign', insufficient: 'Not enough data yet' }[label]
}

export function cards(tc: TimeControlResult): Card[] {
  const out: Card[] = []
  const free = tc.detectors['missed_free']
  const hang = tc.detectors['hanging_own']
  if (free) {
    const r = free.missed_of_available
    out.push({
      key: 'missed_free',
      title: 'Missing free pieces',
      what: 'A piece of theirs was there to take for nothing, and you did not take it.',
      headline: r
        ? `You missed it ${r.k} of ${r.n} times (${pct(r.rate)})`
        : 'No free pieces came up to measure',
      range: r ? `Likely between ${pct(r.ci95[0])} and ${pct(r.ci95[1])}` : '',
      badge: badge(free.label),
      badgeKind: free.label,
      facts: factsFor(free, tc, 'free pieces you could take'),
    })
  }
  if (hang) {
    const r = hang.missed_per_100_moves
    out.push({
      key: 'hanging_own',
      title: 'Leaving your own pieces to be taken',
      what: 'You moved and left one of your pieces for the opponent to win.',
      headline: r
        ? `About ${per100(r.rate)} times in every 100 of your moves (${r.k} times in ${r.n} moves)`
        : 'Nothing to measure',
      range: r ? `Likely between ${per100(r.ci95[0])} and ${per100(r.ci95[1])} per 100 moves` : '',
      badge: badge(hang.label),
      badgeKind: hang.label,
      facts: factsFor(hang, tc, null),
    })
  }
  return out
}

function factsFor(d: DetectorResult, tc: TimeControlResult, chances: string | null): string[] {
  const facts = [`Happened in ${d.games_with_a_miss} of your ${tc.games} games`]
  if (chances) facts.push(`${d.opportunities} ${chances}`)
  if (d.counts.uncertain > 0)
    facts.push(`${d.counts.uncertain} moves were too unclear to judge, so they are left out`)
  return facts
}

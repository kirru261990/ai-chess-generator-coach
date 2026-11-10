export type ZoneName = 'ahead' | 'level' | 'behind'

export interface ZoneResult {
  zone: ZoneName | string
  games: number
  wins: number
  draws: number
  losses: number
  loss_share: { n: number; of: number }
  enough: boolean
}

export interface LeftOut {
  not_analysed: number
  too_short: number
  no_score: number
  unknown_result: number
}

export interface LossMap {
  version: string
  zone_ply: number
  threshold_cp: number
  min_games: number
  depth: number
  games_total: number
  sorted: number
  losses: number
  left_out: LeftOut
  zones: ZoneResult[]
}

export interface ZoneRow {
  key: string
  title: string
  results: string
  bar: { won: number; drawn: number; lost: number }
  lossShare: string | null
  caution: string | null
}

const TITLES: Record<string, string> = {
  ahead: 'Ahead after move 5',
  level: 'Level after move 5',
  behind: 'Behind after move 5',
}

const pct = (n: number, of: number) => Math.round((100 * n) / of)

export function zoneRows(map: LossMap): ZoneRow[] {
  return map.zones.map((z) => {
    const bar =
      z.games > 0 ? { won: pct(z.wins, z.games), drawn: pct(z.draws, z.games), lost: pct(z.losses, z.games) } : { won: 0, drawn: 0, lost: 0 }
    const share =
      z.enough && z.loss_share.of > 0 ? `${pct(z.loss_share.n, z.loss_share.of)}% of your losses (${z.loss_share.n} of ${z.loss_share.of})` : null
    return {
      key: z.zone,
      title: TITLES[z.zone] ?? z.zone,
      results: `${z.wins} won · ${z.draws} drawn · ${z.losses} lost of ${z.games} games`,
      bar,
      lossShare: share,
      caution: z.enough ? null : `Only ${z.games} games here, too few to read a rate (needs ${map.min_games}).`,
    }
  })
}

/** The zone holding the most losses, only when it is clear (no tie) and has enough games to read. */
export function biggestLossZone(map: LossMap): string | null {
  const ranked = [...map.zones].sort((a, b) => b.losses - a.losses)
  const [top, next] = ranked
  if (!top || top.losses === 0 || !top.enough) return null
  if (next && next.losses === top.losses) return null
  return top.zone
}

export function leftOutText(l: LeftOut): string | null {
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
  const parts = [
    l.too_short > 0 ? `${plural(l.too_short, 'game', 'games')} shorter than 5 moves` : null,
    l.not_analysed > 0 ? `${plural(l.not_analysed, 'game', 'games')} not yet analysed` : null,
    l.no_score > 0 ? `${plural(l.no_score, 'game', 'games')} with no clear score` : null,
    l.unknown_result > 0 ? `${plural(l.unknown_result, 'game', 'games')} with an unknown result` : null,
  ].filter((p): p is string => p !== null)
  return parts.length ? `Left out: ${parts.join(', ')}.` : null
}

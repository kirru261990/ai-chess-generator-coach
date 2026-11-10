import { describe, expect, it } from 'vitest'
import { biggestLossZone, leftOutText, zoneRows, type LossMap } from './lossMapState'

const zone = (name: string, games: number, wins: number, draws: number, losses: number, of = 100, enough = true) => ({
  zone: name,
  games,
  wins,
  draws,
  losses,
  loss_share: { n: losses, of },
  enough,
})

const map = (zones: ReturnType<typeof zone>[], left = { not_analysed: 0, too_short: 0, no_score: 0, unknown_result: 0 }): LossMap => ({
  version: '1',
  zone_ply: 10,
  threshold_cp: 50,
  min_games: 10,
  depth: 10,
  games_total: 100,
  sorted: 100,
  losses: 100,
  left_out: left,
  zones,
})

describe('zoneRows', () => {
  it('names each zone for the player and gives results with the number of games they come from', () => {
    const rows = zoneRows(map([zone('ahead', 40, 25, 5, 10, 100)]))
    expect(rows[0].title).toBe('Ahead after move 5')
    expect(rows[0].results).toBe('25 won · 5 drawn · 10 lost of 40 games')
  })

  it('splits the bar in proportion to the results', () => {
    const [r] = zoneRows(map([zone('level', 40, 20, 10, 10)]))
    expect(r.bar).toEqual({ won: 50, drawn: 25, lost: 25 })
  })

  it('shows the share of losses as a rate with its denominator', () => {
    const [r] = zoneRows(map([zone('level', 40, 20, 10, 10, 40)]))
    expect(r.lossShare).toBe('25% of your losses (10 of 40)')
  })

  it('shows no share and says why when a zone has too few games', () => {
    const [r] = zoneRows(map([zone('behind', 4, 1, 0, 3, 40, false)]))
    expect(r.lossShare).toBeNull()
    expect(r.caution).toBe('Only 4 games here, too few to read a rate (needs 10).')
  })

  it('has an empty bar rather than a division by zero for a zone with no games', () => {
    const [r] = zoneRows(map([zone('ahead', 0, 0, 0, 0, 0, false)]))
    expect(r.bar).toEqual({ won: 0, drawn: 0, lost: 0 })
  })
})

describe('biggestLossZone', () => {
  it('names the zone holding the most losses when it is clear and has enough games', () => {
    expect(biggestLossZone(map([zone('ahead', 40, 20, 5, 15), zone('level', 40, 10, 5, 25)]))).toBe('level')
  })

  it('names none on a tie', () => {
    expect(biggestLossZone(map([zone('ahead', 40, 20, 5, 15), zone('level', 40, 20, 5, 15)]))).toBeNull()
  })

  it('names none when the biggest zone has too few games', () => {
    expect(biggestLossZone(map([zone('ahead', 4, 0, 0, 4, 4, false), zone('level', 40, 20, 5, 0)]))).toBeNull()
  })
})

describe('leftOutText', () => {
  it('says nothing when every game was sorted', () => {
    expect(leftOutText(map([]).left_out)).toBeNull()
  })

  it('lists each reason with its count', () => {
    expect(leftOutText({ not_analysed: 2, too_short: 9, no_score: 0, unknown_result: 1 })).toBe(
      'Left out: 9 games shorter than 5 moves, 2 games not yet analysed, 1 game with an unknown result.',
    )
  })
})

/**
 * Draw a move on a position before the server has answered (the chat board shows the player's move at the click). DISPLAY ONLY:
 * the server stays the authority on rules and state (AGENTS rule 1), and its position replaces this one when it arrives. The page
 * only passes moves taken from the server's legal move list, so this does not check legality; it just moves the pieces, including
 * capture, en passant, castling (king and rook) and promotion, and keeps the rest of the FEN consistent.
 */
const FILES = 'abcdefgh'

type Grid = (string | null)[][] // grid[rank 0..7 from rank 8 down][file 0..7]

const parse = (placement: string): Grid =>
  placement.split('/').map((row) => {
    const out: (string | null)[] = []
    for (const ch of row) {
      if (/\d/.test(ch)) for (let i = 0; i < Number(ch); i++) out.push(null)
      else out.push(ch)
    }
    return out
  })

const write = (g: Grid): string =>
  g
    .map((row) => {
      let s = ''
      let empty = 0
      for (const p of row) {
        if (p === null) empty++
        else {
          if (empty) s += empty
          empty = 0
          s += p
        }
      }
      return empty ? s + empty : s
    })
    .join('/')

const at = (sq: string) => ({ f: FILES.indexOf(sq[0]), r: 8 - Number(sq[1]) })

export function applyMove(fen: string, uci: string): string {
  const [placement, , castling, , half, full] = fen.split(' ')
  const g = parse(placement)
  const from = at(uci.slice(0, 2))
  const to = at(uci.slice(2, 4))
  const piece = g[from.r][from.f]
  if (!piece) return fen // nothing to move: leave the position alone
  const white = piece === piece.toUpperCase()
  const isPawn = piece.toLowerCase() === 'p'
  const captured = g[to.r][to.f]
  g[from.r][from.f] = null
  let placed = piece
  if (isPawn && uci.length === 5) placed = white ? uci[4].toUpperCase() : uci[4].toLowerCase()
  if (isPawn && from.f !== to.f && !captured) g[from.r][to.f] = null // en passant: the captured pawn stands beside the start square
  g[to.r][to.f] = placed
  if (piece.toLowerCase() === 'k' && Math.abs(to.f - from.f) === 2) {
    const rookFrom = to.f > from.f ? 7 : 0
    const rookTo = to.f > from.f ? 5 : 3
    g[to.r][rookTo] = g[to.r][rookFrom]
    g[to.r][rookFrom] = null
  }
  let rights = castling === '-' ? '' : castling
  const drop = (letters: string) => {
    for (const c of letters) rights = rights.replace(c, '')
  }
  if (piece === 'K') drop('KQ')
  if (piece === 'k') drop('kq')
  for (const sq of [uci.slice(0, 2), uci.slice(2, 4)]) {
    if (sq === 'h1') drop('K')
    if (sq === 'a1') drop('Q')
    if (sq === 'h8') drop('k')
    if (sq === 'a8') drop('q')
  }
  const newEp = isPawn && Math.abs(to.r - from.r) === 2 ? `${uci[0]}${(Number(uci[1]) + Number(uci[3])) / 2}` : '-'
  const reset = isPawn || captured !== null
  const halfmove = reset ? 0 : Number(half ?? 0) + 1
  const fullmove = Number(full ?? 1) + (white ? 0 : 1)
  return [write(g), white ? 'b' : 'w', rights || '-', newEp, halfmove, fullmove].join(' ')
}

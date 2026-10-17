import { describe, expect, it } from 'vitest'
import { applyMove } from './applyMove'

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

describe('applyMove (display only)', () => {
  it('plays a pawn double step, sets the en passant square, flips the side', () => {
    expect(applyMove(START, 'e2e4')).toBe('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1')
  })
  it('counts the move number after Black moves and the halfmove clock for quiet piece moves', () => {
    const f = applyMove('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1', 'g8f6')
    expect(f).toBe('rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2')
  })
  it('captures a piece and resets the halfmove clock', () => {
    expect(applyMove('4k3/8/8/3p4/4P3/8/8/4K3 w - - 5 10', 'e4d5')).toBe('4k3/8/8/3P4/8/8/8/4K3 b - - 0 10')
  })
  it('captures en passant, removing the pawn beside the start square', () => {
    expect(applyMove('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 3', 'e5d6')).toBe('4k3/8/3P4/8/8/8/8/4K3 b - - 0 3')
    expect(applyMove('4k3/8/8/8/3pP3/8/8/4K3 b - e3 0 3', 'd4e3')).toBe('4k3/8/8/8/8/4p3/8/4K3 w - - 0 4')
  })
  it('castles both ways for both colours, moving the rook and dropping the rights', () => {
    const w = 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
    expect(applyMove(w, 'e1g1')).toBe('r3k2r/8/8/8/8/8/8/R4RK1 b kq - 1 1')
    expect(applyMove(w, 'e1c1')).toBe('r3k2r/8/8/8/8/8/8/2KR3R b kq - 1 1')
    const b = 'r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1'
    expect(applyMove(b, 'e8g8')).toBe('r4rk1/8/8/8/8/8/8/R3K2R w KQ - 1 2')
    expect(applyMove(b, 'e8c8')).toBe('2kr3r/8/8/8/8/8/8/R3K2R w KQ - 1 2')
  })
  it('drops castling rights when a rook moves or is captured', () => {
    expect(applyMove('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', 'h1h5')).toBe('r3k2r/8/8/7R/8/8/8/R3K3 b Qkq - 1 1')
    expect(applyMove('r3k2r/8/8/8/8/8/6B1/R3K2R w KQkq - 0 1', 'g2a8')).toBe('B3k2r/8/8/8/8/8/8/R3K2R b KQk - 0 1')
  })
  it('promotes to the chosen piece, with or without a capture', () => {
    expect(applyMove('4k3/P7/8/8/8/8/8/4K3 w - - 0 1', 'a7a8q')).toBe('Q3k3/8/8/8/8/8/8/4K3 b - - 0 1')
    expect(applyMove('1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1', 'a7b8n')).toBe('1N2k3/8/8/8/8/8/8/4K3 b - - 0 1')
    expect(applyMove('4k3/8/8/8/8/8/p7/4K3 b - - 0 1', 'a2a1r')).toBe('4k3/8/8/8/8/8/8/r3K3 w - - 0 2')
  })
  it('leaves the position alone when there is nothing to move', () => {
    expect(applyMove(START, 'e4e5')).toBe(START)
  })
})

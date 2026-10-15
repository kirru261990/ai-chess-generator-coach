import { describe, expect, it } from 'vitest'
import { castleMove, leftOutLine, pickMove, scoreNotes, tapRefusal, pieceColorAt, poolShortfall, scoreLine, startLabel, tapWords, targetsFrom, type HomeType } from './assessState'

const pool = { mistake_positions: 20, clean_positions: 30, needed_mistake_positions: 16, needed_clean_positions: 8, ready: true }
const home = (over: Partial<HomeType>): HomeType => ({ mistake_type: 'M1', label: 'x', pool, baseline: null, ...over })

describe('startLabel', () => {
  it('starts, continues or shows results, and cannot start a small pool', () => {
    expect(startLabel(home({}))).toBe('Start the test')
    expect(startLabel(home({ baseline: { assessment_id: 1, status: 'in_progress' } }))).toBe('Continue the test')
    expect(startLabel(home({ baseline: { assessment_id: 1, status: 'submitted' } }))).toBe('See my results')
    expect(startLabel(home({ pool: { ...pool, ready: false } }))).toBeNull()
  })
})

describe('poolShortfall', () => {
  it('shows the counts when the pool is too small', () => {
    expect(poolShortfall(pool)).toBeNull()
    expect(poolShortfall({ ...pool, mistake_positions: 3, ready: false })).toContain('3 of 16 mistake positions')
  })
})

describe('board helpers', () => {
  const fen = '4k3/4q2R/8/8/8/8/3B4/6K1 w - - 0 1'
  it('reads piece colours from a FEN', () => {
    expect(pieceColorAt(fen, 'h7')).toBe('w')
    expect(pieceColorAt(fen, 'e7')).toBe('b')
    expect(pieceColorAt(fen, 'e4')).toBeNull()
    expect(pieceColorAt(fen, 'z9')).toBeNull()
  })
  it('picks legal moves and promotes to a queen', () => {
    const legal = ['h7h1', 'h7h2', 'a7a8q', 'a7a8n']
    expect(pickMove(legal, 'h7', 'h1')).toBe('h7h1')
    expect(pickMove(legal, 'a7', 'a8')).toBe('a7a8q')
    expect(pickMove(legal, 'h7', 'a1')).toBeNull()
    expect(targetsFrom(legal, 'h7')).toEqual(['h1', 'h2'])
    expect(targetsFrom(legal, null)).toEqual([])
  })
})

describe('castling', () => {
  const fen = 'r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1'
  const legal = ['e8c8', 'e8g8', 'e8d8', 'a8a1']
  it('treats king then own rook as castling on that side', () => {
    expect(castleMove(legal, fen, 'e8', 'a8')).toBe('e8c8')
    expect(castleMove(legal, fen, 'e8', 'h8')).toBe('e8g8')
  })
  it('only when legal, and only king then own rook', () => {
    expect(castleMove(['e8d8'], fen, 'e8', 'a8')).toBeNull()
    expect(castleMove(legal, fen, 'a8', 'e8')).toBeNull()
    expect(castleMove(legal, fen, 'e8', 'a1')).toBeNull()
  })
})

describe('tapRefusal', () => {
  const squares = ['a1', 'e1']
  it('accepts a piece of the asked side', () => {
    expect(tapRefusal(null, 'a1', squares, 'M1')).toBeNull()
    expect(tapRefusal('e1', 'a1', squares, 'M1')).toBeNull() // changing a tapped piece is fine
  })
  it('explains a tap on the other side, for each type', () => {
    expect(tapRefusal(null, 'h8', squares, 'M1')).toContain('your own')
    expect(tapRefusal(null, 'h8', squares, 'M2')).toContain('their')
  })
  it('never lets a board click replace "No immediate threat"', () => {
    expect(tapRefusal('none', 'a1', squares, 'M1')).toContain('Press that button again')
  })
})

describe('leftOutLine', () => {
  it('says how many positions were left out, or nothing', () => {
    expect(leftOutLine(0)).toBeNull()
    expect(leftOutLine(1)).toContain('1 position was left out')
    expect(leftOutLine(2)).toContain('2 positions were left out')
  })
})

describe('scoreNotes', () => {
  it('shows a version 1 note and a set-aside notice, and nothing for a current test', () => {
    expect(scoreNotes({ notes: [], set_aside: false })).toEqual([])
    expect(scoreNotes({ notes: ['not comparable'], set_aside: false })).toEqual(['not comparable'])
    expect(scoreNotes({ notes: [], set_aside: true })[0]).toContain('set aside')
  })
})

describe('words', () => {
  it('always puts a score next to its guessing rate', () => {
    expect(scoreLine(3, 5, 0.94)).toBe('3 of 5 (guessing would get about 0.9)')
    expect(scoreLine(3, 5, null)).toBe('3 of 5 (guessing: still calculating)')
    expect(scoreLine(1, 5, 0.02)).toBe('1 of 5 (guessing would get almost none)')
    expect(tapWords('none')).toBe('"No immediate threat"')
    expect(tapWords('h7')).toBe('the piece on h7')
  })
})

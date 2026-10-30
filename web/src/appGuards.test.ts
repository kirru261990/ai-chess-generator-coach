import { describe, expect, it } from 'vitest'
import source from './App.tsx?raw'

// react-chessboard skips its own square styling (move dots, red and green marks, hint tint) when a custom squareRenderer
// returns something. There is no browser test here, so this guards the one line that keeps those styles alive.
describe('the board keeps its square styles when the move badge is drawn', () => {
  it('applies the shared square styles inside the custom square renderer', () => {
    const renderer = source.slice(source.indexOf('const squareRenderer'))
    expect(renderer.slice(0, 400)).toContain('...boardStyles[square]')
  })

  it('passes the same styles to the board itself', () => {
    expect(source).toContain('squareStyles: boardStyles')
  })
})

// There is no browser test here, so these guard the startup race: the automatic first game must not replace one the player started.
describe('the automatic first game waits for the opponent probe', () => {
  it('locks every control and New game until /opponents settles', () => {
    const controls = source.slice(source.indexOf('<div className="controls">'), source.indexOf('{game && ('))
    expect(controls.match(/<select disabled=\{probing\}/g)).toHaveLength(5)
    expect(controls).toContain('disabled={busy || probing}')
  })

  it('unlocks them when the probe settles, and gives up on a hung probe', () => {
    expect(source).toContain('setProbing(false)')
    expect(source).toContain('signal: AbortSignal.timeout(PROBE_TIMEOUT_MS)')
  })
})

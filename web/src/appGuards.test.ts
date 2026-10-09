import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// react-chessboard skips its own square styling (move dots, red and green marks, hint tint) when a custom squareRenderer
// returns something. There is no browser test here, so this guards the one line that keeps those styles alive.
describe('the board keeps its square styles when the move badge is drawn', () => {
  const source = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8')

  it('applies the shared square styles inside the custom square renderer', () => {
    const renderer = source.slice(source.indexOf('const squareRenderer'))
    expect(renderer.slice(0, 400)).toContain('...boardStyles[square]')
  })

  it('passes the same styles to the board itself', () => {
    expect(source).toContain('squareStyles: boardStyles')
  })
})

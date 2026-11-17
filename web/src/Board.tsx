import { Chessboard as LibChessboard } from 'react-chessboard'
import type { ComponentProps } from 'react'

// Tournament green: the board in the masthead's own green family. Every board in the app goes through this wrapper so
// the colours stay one set; a board's own options still win.
const THEME = {
  lightSquareStyle: { backgroundColor: '#e9eedf' },
  darkSquareStyle: { backgroundColor: '#5e8a72' },
  lightSquareNotationStyle: { color: '#3f6b55' },
  darkSquareNotationStyle: { color: '#e9eedf' },
}

export function Chessboard({ options, ...rest }: ComponentProps<typeof LibChessboard>) {
  return <LibChessboard {...rest} options={{ ...THEME, ...options }} />
}

import { App } from '@modelcontextprotocol/ext-apps'
import { StrictMode, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import '../App.css'
import GameBoard, { type Enlarge } from '../GameBoard'
import { gameToolBackend, isGamePayload, type GamePayload } from '../gameBackend'
import Practice from '../Practice'
import { toolBackend, type BoardPayload, type ToolCaller } from '../practiceBackend'

/** The board inside a chat (an MCP app). The chat shows this page in a sandbox: it hands over the result of the tool that showed the
 *  board, and this page calls the same tools for every click, so the rules and the engine stay on the server. One file serves two
 *  pages: Replay My Mistakes practice (ADR 0008) and a game against Stockfish, Play or Practice (ADR 0009); the latest tool result
 *  decides which. */
const app = new App({ name: 'chess-coach-board', version: '1.0.0' })

const call: ToolCaller = async (name, args) => {
  const r = await app.callServerTool({ name, arguments: args })
  const text = r.content?.find((c) => c.type === 'text')
  return { structured: r.structuredContent ?? null, text: text && 'text' in text ? String(text.text) : '' }
}

type Shown = { kind: 'practice'; payload: BoardPayload } | { kind: 'game'; payload: GamePayload }

/** The chat's bigger view, when the host offers one (`availableDisplayModes`); null if it does not. The host answers with the mode it
 *  actually set, which may differ from the one asked for. */
function useEnlarge(): Enlarge | null {
  const [mode, setMode] = useState<string>('inline')
  const [offered, setOffered] = useState(false)
  useEffect(() => {
    const read = (ctx?: { displayMode?: string; availableDisplayModes?: string[] }) => {
      if (!ctx) return
      if (ctx.displayMode) setMode(ctx.displayMode)
      if (ctx.availableDisplayModes) setOffered(ctx.availableDisplayModes.includes('fullscreen'))
    }
    app.onhostcontextchanged = (ctx) => read(ctx)
    const t = setTimeout(() => read(app.getHostContext()), 500) // the first context arrives with the handshake
    return () => clearTimeout(t)
  }, [])
  const toggle = () => {
    const next = mode === 'fullscreen' ? 'inline' : 'fullscreen'
    app.requestDisplayMode({ mode: next }).then((r) => setMode(r.mode), () => undefined)
  }
  return offered ? { large: mode === 'fullscreen', toggle } : null
}

function Board() {
  const [shown, setShown] = useState<Shown | null>(null)
  const enlarge = useEnlarge()
  const practiceBackend = useMemo(() => toolBackend(call), [])
  const gameBackend = useMemo(() => gameToolBackend(call), [])
  useEffect(() => {
    // Set the handler before connecting: the host may send the result right after the handshake.
    app.ontoolresult = (params) => {
      const data = params.structuredContent
      if (isGamePayload(data)) setShown({ kind: 'game', payload: data })
      else if ((data as BoardPayload | undefined)?.view) setShown({ kind: 'practice', payload: data as BoardPayload })
    }
    app.connect().catch(() => {})
  }, [])
  if (!shown) return <div className="app"><p className="note">Waiting for the board…</p></div>
  if (shown.kind === 'game') return <GameBoard key={shown.payload.game.id} initial={shown.payload} backend={gameBackend} enlarge={enlarge ?? undefined} />
  const p = shown.payload
  return <Practice key={p.view.session_id} id={p.view.session_id} backend={practiceBackend} initial={p} />
}

createRoot(document.getElementById('root')!).render(<StrictMode><Board /></StrictMode>)

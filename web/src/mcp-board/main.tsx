import { App } from '@modelcontextprotocol/ext-apps'
import { StrictMode, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import '../App.css'
import Practice from '../Practice'
import { toolBackend, type BoardPayload, type ToolCaller } from '../practiceBackend'

/** The practice board inside a chat (an MCP app). The chat shows this page in a sandbox: it hands over the result of the tool that
 *  showed the board, and this page calls the same practice tools for every click, so the rules and the engine stay on the server. */
const app = new App({ name: 'chess-coach-board', version: '1.0.0' })

const call: ToolCaller = async (name, args) => {
  const r = await app.callServerTool({ name, arguments: args })
  const text = r.content?.find((c) => c.type === 'text')
  return { structured: r.structuredContent ?? null, text: text && 'text' in text ? String(text.text) : '' }
}

function Board() {
  const [payload, setPayload] = useState<BoardPayload | null>(null)
  const backend = useMemo(() => toolBackend(call), [])
  useEffect(() => {
    // Set the handler before connecting: the host may send the result right after the handshake.
    app.ontoolresult = (params) => {
      const data = params.structuredContent as BoardPayload | undefined
      if (data?.view) setPayload(data)
    }
    app.connect().catch(() => {})
  }, [])
  if (!payload) return <div className="app"><p className="note">Waiting for the board…</p></div>
  return <Practice key={payload.view.session_id} id={payload.view.session_id} backend={backend} initial={payload} />
}

createRoot(document.getElementById('root')!).render(<StrictMode><Board /></StrictMode>)

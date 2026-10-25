/** The chat's side of the MCP Apps protocol (JSON-RPC over postMessage), only what the board uses. It replaces
 *  `@modelcontextprotocol/ext-apps`' `App`, whose client and schema libraries were over half of the board page (about 560 KB, past
 *  512 KiB, a size some hosts refuse). The messages are the ones that library sends, recorded from a real run:
 *  ui/initialize (request), ui/notifications/initialized, tools/call, ui/request-display-mode, ui/notifications/size-changed; it answers
 *  ping and ui/resource-teardown and takes ui/notifications/tool-result and host-context-changed. */

export type HostContext = { displayMode?: string; availableDisplayModes?: string[]; [k: string]: unknown }
export type ToolResult = { content?: { type: string; text?: string }[]; structuredContent?: unknown; isError?: boolean }

export const PROTOCOL_VERSION = '2026-01-26' // the version the replaced library announces
export const REQUEST_TIMEOUT_MS = 60_000

type Wire = { jsonrpc: '2.0'; id?: number; method?: string; params?: unknown; result?: unknown; error?: { code: number; message: string } }
type Pending = { resolve: (v: unknown) => void; reject: (e: Error) => void }

export class MiniApp {
  ontoolresult?: (params: ToolResult) => void
  onhostcontextchanged?: (ctx: HostContext) => void
  private ctx: HostContext | undefined
  private next = 0
  private pending = new Map<number, Pending>()

  private info: { name: string; version: string }
  private host: { postMessage(m: unknown, target: string): void }
  private win: Pick<Window, 'addEventListener'>

  constructor(
    info: { name: string; version: string },
    host: { postMessage(m: unknown, target: string): void } = window.parent,
    win: Pick<Window, 'addEventListener'> = window,
  ) {
    this.info = info
    this.host = host
    this.win = win
  }

  getHostContext(): HostContext | undefined {
    return this.ctx
  }

  /** Start taking the chat's messages (connect() does this first). */
  listen() {
    this.win.addEventListener('message', (e) => {
      if ((e as MessageEvent).source !== (this.host as unknown)) return // only the chat that holds this page
      this.receive((e as MessageEvent).data)
    })
  }

  async connect(): Promise<void> {
    this.listen()
    const init = (await this.request('ui/initialize', {
      appCapabilities: {}, appInfo: this.info, protocolVersion: PROTOCOL_VERSION,
    })) as { hostContext?: HostContext } | undefined
    if (init === undefined) throw new Error('the chat sent an empty answer to ui/initialize')
    this.ctx = init.hostContext
    this.send({ jsonrpc: '2.0', method: 'ui/notifications/initialized' })
    this.watchSize()
  }

  callServerTool(p: { name: string; arguments: Record<string, unknown> }): Promise<ToolResult> {
    return this.request('tools/call', p) as Promise<ToolResult>
  }

  requestDisplayMode(p: { mode: string }): Promise<{ mode: string }> {
    return this.request('ui/request-display-mode', p) as Promise<{ mode: string }>
  }

  private send(m: Wire) {
    this.host.postMessage(m, '*')
  }

  private request(method: string, params: unknown): Promise<unknown> {
    const id = this.next++
    return new Promise((resolve, reject) => {
      // A lost answer must not leave the page waiting for ever (its buttons stay off while a call is open): give up as the
      // replaced library did, after 60 seconds.
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error('Request timed out'))
      }, REQUEST_TIMEOUT_MS)
      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v) },
        reject: (e) => { clearTimeout(timer); reject(e) },
      })
      this.send({ jsonrpc: '2.0', id, method, params })
    })
  }

  receive(m: Wire) {
    if (!m || m.jsonrpc !== '2.0') return // not ours
    if (m.id !== undefined && m.method === undefined) { // an answer to one of our requests
      const p = this.pending.get(m.id)
      if (!p) return
      this.pending.delete(m.id)
      if (m.error) p.reject(new Error(m.error.message))
      else p.resolve(m.result)
    } else if (m.id !== undefined) { // the chat asks us something
      if (m.method === 'ping' || m.method === 'ui/resource-teardown') this.send({ jsonrpc: '2.0', id: m.id, result: {} })
      else this.send({ jsonrpc: '2.0', id: m.id, error: { code: -32601, message: `method not found: ${m.method}` } })
    } else if (m.method === 'ui/notifications/tool-result') {
      this.ontoolresult?.(m.params as ToolResult)
    } else if (m.method === 'ui/notifications/host-context-changed') {
      const change = (m.params ?? {}) as HostContext
      this.ctx = { ...this.ctx, ...change }
      this.onhostcontextchanged?.(change)
    }
  }

  /** Tell the chat how tall the page is, so it can size the frame (what the replaced library's autoResize does). */
  private watchSize() {
    if (typeof document === 'undefined') return // no page to measure (tests)
    let queued = false
    let lastW = 0
    let lastH = 0
    const report = () => {
      if (queued) return
      queued = true
      requestAnimationFrame(() => {
        queued = false
        const el = document.documentElement
        const was = el.style.height
        el.style.height = 'max-content'
        const height = Math.ceil(el.getBoundingClientRect().height)
        el.style.height = was
        const width = Math.ceil(window.innerWidth)
        if (width !== lastW || height !== lastH) {
          lastW = width
          lastH = height
          this.send({ jsonrpc: '2.0', method: 'ui/notifications/size-changed', params: { width, height } })
        }
      })
    }
    report()
    const ro = new ResizeObserver(report)
    ro.observe(document.documentElement)
    ro.observe(document.body)
  }
}

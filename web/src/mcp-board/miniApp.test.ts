import { describe, expect, it } from 'vitest'
import { MiniApp, PROTOCOL_VERSION } from './miniApp'

function rig() {
  const sent: any[] = []
  const host = { postMessage: (m: unknown) => sent.push(m) }
  let listener: (e: any) => void = () => {}
  const win = { addEventListener: (_: string, f: (e: any) => void) => { listener = f } }
  const app = new MiniApp({ name: 'board', version: '1' }, host, win as any)
  const fromHost = (data: unknown) => listener({ source: host, data })
  return { app, sent, fromHost, listener: (e: any) => listener(e), host }
}

describe('the chat bridge', () => {
  it('connects with ui/initialize, then announces itself, and keeps the chat context', async () => {
    const r = rig()
    const done = r.app.connect()
    expect(r.sent[0]).toEqual({ jsonrpc: '2.0', id: 0, method: 'ui/initialize',
      params: { appCapabilities: {}, appInfo: { name: 'board', version: '1' }, protocolVersion: PROTOCOL_VERSION } })
    r.fromHost({ jsonrpc: '2.0', id: 0, result: { hostContext: { displayMode: 'inline', availableDisplayModes: ['inline', 'fullscreen'] } } })
    await done
    expect(r.sent[1]).toEqual({ jsonrpc: '2.0', method: 'ui/notifications/initialized' })
    expect(r.app.getHostContext()?.availableDisplayModes).toContain('fullscreen')
  })

  it('answers a tool call with the result, and a refusal with an error', async () => {
    const r = rig()
    r.app.listen()
    const ok = r.app.callServerTool({ name: 'game_show', arguments: { game_id: 'g' } })
    expect(r.sent[0]).toMatchObject({ method: 'tools/call', params: { name: 'game_show', arguments: { game_id: 'g' } } })
    r.fromHost({ jsonrpc: '2.0', id: r.sent[0].id, result: { structuredContent: { a: 1 } } })
    expect((await ok).structuredContent).toEqual({ a: 1 })
    const bad = r.app.callServerTool({ name: 'x', arguments: {} })
    r.fromHost({ jsonrpc: '2.0', id: r.sent[1].id, error: { code: -1, message: 'no' } })
    await expect(bad).rejects.toThrow('no')
  })

  it('hands over tool results and context changes, and answers ping and teardown', () => {
    const r = rig()
    r.app.listen()
    const seen: unknown[] = []
    r.app.ontoolresult = (p) => seen.push(p)
    r.app.onhostcontextchanged = (c) => seen.push(c)
    r.fromHost({ jsonrpc: '2.0', method: 'ui/notifications/tool-result', params: { structuredContent: { kind: 'game' } } })
    r.fromHost({ jsonrpc: '2.0', method: 'ui/notifications/host-context-changed', params: { displayMode: 'fullscreen' } })
    expect(seen).toEqual([{ structuredContent: { kind: 'game' } }, { displayMode: 'fullscreen' }])
    expect(r.app.getHostContext()?.displayMode).toBe('fullscreen')
    r.fromHost({ jsonrpc: '2.0', id: 7, method: 'ping' })
    r.fromHost({ jsonrpc: '2.0', id: 8, method: 'ui/resource-teardown' })
    r.fromHost({ jsonrpc: '2.0', id: 9, method: 'something/else' })
    expect(r.sent).toEqual([
      { jsonrpc: '2.0', id: 7, result: {} }, { jsonrpc: '2.0', id: 8, result: {} },
      { jsonrpc: '2.0', id: 9, error: { code: -32601, message: 'method not found: something/else' } },
    ])
  })

  it('ignores messages from anyone but the chat and anything that is not JSON-RPC', async () => {
    const r = rig()
    const done = r.app.connect()
    r.listener({ source: {}, data: { jsonrpc: '2.0', id: 0, result: { hostContext: {} } } }) // a stranger: ignored
    r.fromHost('hello')
    r.fromHost({ nope: true })
    let settled = false
    void done.then(() => (settled = true))
    await Promise.resolve()
    expect(settled).toBe(false)
    r.fromHost({ jsonrpc: '2.0', id: 0, result: {} })
    await done
  })
})

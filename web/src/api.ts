export const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** GET, or POST when a body is given. Throws the server's plain-words message on an error; the error also carries the server's `code`. */
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (!res.ok) throw Object.assign(new Error(data.message ?? data.error ?? `request failed (${res.status})`), { code: data.error as string | undefined, status: res.status })
  return data as T
}

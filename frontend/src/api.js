export const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function req(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* not json */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json()
}

export const api = {
  health: () => req('/health'),
  nodes: () => req('/nodes'),
  products: () => req('/products'),
  mops: () => req('/mops'),
  tickets: (status) => req(`/tickets${status ? `?status=${status}` : ''}`),
  cases: (params = {}) => req(`/cases?${new URLSearchParams(params)}`),
  case: (id) => req(`/cases/${encodeURIComponent(id)}`),
  deleteCase: (id) => req(`/cases/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  trends: () => req('/trends'),
  digest: (days = 30) => req(`/digest?days=${days}`),
  notifications: () => req('/notifications'),
  feedback: (body) => req('/feedback', { method: 'POST', body }),
  fingerprint: (body) => req('/fingerprint', { method: 'POST', body }),
  lessonOptions: () => req('/lesson-options'),
}

/** POST /recommend/stream and call onEvent for every Server-Sent Event (agent trace, LLM tokens, final). */
export async function streamRecommend(body, onEvent, signal) {
  const res = await fetch(`${API}/recommend/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) throw new Error(await res.text())
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let i
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const raw = buf.slice(0, i)
      buf = buf.slice(i + 2)
      const line = raw.split('\n').find((l) => l.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)))
    }
  }
}

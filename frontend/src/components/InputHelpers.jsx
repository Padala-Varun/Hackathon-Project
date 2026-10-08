import { useEffect, useState } from 'react'
import { ScanSearch, Sparkles } from 'lucide-react'
import { api } from '../api'

/** "Try an example" chips: examples = [{ label, text, ...extra }]. */
export function ExampleChips({ examples, onPick }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="inline-flex items-center gap-1 text-xs font-medium text-subtle"><Sparkles size={13} /> Try an example:</span>
      {examples.map((ex) => (
        <button key={ex.label} onClick={() => onPick(ex)} title={ex.text}
          className="rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted transition hover:border-accent/60 hover:bg-accent/10 hover:text-fg">
          {ex.label}
        </button>
      ))}
    </div>
  )
}

/** Live preview of what the agent detects in the text (node, MOP, release, error codes). */
export function DetectedChips({ text, node, mop, release, mode, nodeType, showMop = true, showNode = true }) {
  const [fp, setFp] = useState(null)
  useEffect(() => {
    if (!text.trim()) { setFp(null); return }
    const t = setTimeout(() => {
      api.fingerprint({ text, node: node || null, mop_id: mop || null, release: release || null, node_type: nodeType || null }).then(setFp).catch(() => setFp(null))
    }, 400)
    return () => clearTimeout(t)
  }, [text, node, mop, release, nodeType])

  if (!fp) return null
  const items = [
    ...(showNode ? [['Node', fp.nodes[0]]] : []),
    ['Product', fp.node_types[0]],
    ...(mode === 'pre_change' ? [...(showMop ? [['MOP', fp.mop_ids[0]]] : []), ['Release', fp.releases[0]]] : []),
    ...(fp.error_signatures.length ? [['Error', fp.error_signatures.slice(0, 2).join(', ')]] : []),
  ]
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className="inline-flex items-center gap-1 font-medium text-subtle"><ScanSearch size={13} /> Detected:</span>
      {items.map(([k, v]) => (
        <span key={k} className={`rounded-md border px-1.5 py-0.5 ${v ? 'border-ok/30 bg-ok/8 text-fg' : 'border-dashed border-line-strong text-subtle'}`}>
          <span className="text-subtle">{k}</span> {v || 'not found'}
        </span>
      ))}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { api } from '../api'
import { Pill, Spinner } from './ui'

const FIELDS = [
  ['description', 'Description'], ['symptoms', 'Symptoms'], ['error_signature', 'Error signature'], ['commands', 'Commands'],
  ['root_cause', 'Root cause'], ['resolution', 'Resolution'], ['learning', 'Learning / pre-check'],
]

export default function RecordModal({ id, onClose }) {
  const [r, setR] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    setR(null); setErr('')
    api.case(id).then(setR).catch((e) => setErr(e.message))
  }, [id])

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 pt-16" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-xl border border-ink-700 bg-ink-900 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-center gap-2 border-b border-ink-800 px-5 py-3">
          <span className="font-mono text-sm text-info">{id}</span>
          {r?.source === 'learning' && <Pill tone="ok">verified learning · {r.verified_by}</Pill>}
          <button onClick={onClose} className="ml-auto text-ink-500 hover:text-ink-100">✕</button>
        </header>
        <div className="space-y-3 p-5 text-sm">
          {!r && !err && <Spinner />}
          {err && <p className="text-bad">{err}</p>}
          {r && (
            <>
              <h3 className="text-base font-semibold text-ink-100">{r.title}</h3>
              <div className="flex flex-wrap gap-1.5">
                {[r.date, r.node, r.node_type, r.vendor, r.release && `rel ${r.release}`, r.change_type,
                  r.mop_id && `${r.mop_id}${r.mop_step ? ` step ${r.mop_step}` : ''}`, r.outcome, r.severity && `${r.severity} severity`]
                  .filter(Boolean).map((x) => <Pill key={x}>{x}</Pill>)}
              </div>
              {FIELDS.filter(([k]) => r[k]).map(([k, label]) => (
                <div key={k}>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-amber">{label}</p>
                  <p className={`leading-relaxed text-ink-100 ${k === 'commands' ? 'font-mono text-xs' : ''}`}>{r[k]}</p>
                </div>
              ))}
              {r.related_ids?.length > 0 && <p className="text-xs text-ink-500">Related: {r.related_ids.join(', ')}</p>}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

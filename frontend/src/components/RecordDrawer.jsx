import { useEffect, useState } from 'react'
import { BadgeCheck, X } from 'lucide-react'
import { api } from '../api'
import { Badge, formatTs, outcomeTone, Skeleton } from './ui'

const FIELDS = [
  ['description', 'What was done'], ['symptoms', 'Problem / symptoms'], ['error_signature', 'Error signature'],
  ['commands', 'Commands'], ['root_cause', 'Root cause'], ['resolution', 'Fix'], ['learning', 'Learning / pre-check'],
]

/** Slide-over panel showing one full source record (the "proof" behind a citation). */
export default function RecordDrawer({ id, onClose }) {
  const [r, setR] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    setR(null); setErr('')
    api.case(id).then(setR).catch((e) => setErr(e.message))
  }, [id])
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50">
      <div className="animate-fade-in absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="animate-drawer absolute inset-y-0 right-0 flex w-full max-w-xl flex-col border-l border-line bg-surface shadow-pop">
        <header className="flex items-center gap-2 border-b border-line px-6 py-4">
          <span className="font-mono text-sm font-semibold text-link">{id}</span>
          {r?.source === 'learning' && <Badge tone="ok" icon={BadgeCheck}>Verified lesson · {r.verified_by}{r.verified_at ? ` · ${formatTs(r.verified_at)}` : ''}</Badge>}
          <span className="text-xs text-subtle">Source record</span>
          <button onClick={onClose} className="ml-auto rounded-md p-1 text-subtle hover:bg-surface-3 hover:text-fg" aria-label="Close"><X size={18} /></button>
        </header>
        <div className="scroll-thin flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {err && <p className="text-sm text-bad">{err}</p>}
          {!r && !err && (
            <div className="space-y-3"><Skeleton className="h-6 w-3/4" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-20" /><Skeleton className="h-20" /></div>
          )}
          {r && (
            <>
              <div>
                <h3 className="text-lg leading-snug font-semibold text-fg">{r.title}</h3>
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {r.outcome && <Badge tone={outcomeTone(r.outcome)}>{r.outcome}</Badge>}
                  {[r.date, r.node, r.node_type, r.vendor, r.release && `Release ${r.release}`, r.change_type,
                    r.mop_id && `${r.mop_id}${r.mop_step ? ` · step ${r.mop_step}` : ''}`, r.severity && `${r.severity} severity`]
                    .filter(Boolean).map((x) => <Badge key={x}>{x}</Badge>)}
                </div>
              </div>
              {FIELDS.filter(([k]) => r[k]).map(([k, label]) => (
                <div key={k}>
                  <p className="mb-1 text-xs font-semibold tracking-wide text-subtle uppercase">{label}</p>
                  <p className={`text-sm leading-relaxed whitespace-pre-wrap text-fg ${k === 'commands' || k === 'error_signature' || (k === 'resolution' && r[k].length > 400) ? 'scroll-thin max-h-[28rem] overflow-auto rounded-lg bg-surface-3 px-3 py-2 font-mono text-[12.5px]' : ''}`}>{r[k]}</p>
                </div>
              ))}
              {Object.keys(r.extra || {}).length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs font-semibold tracking-wide text-subtle uppercase">Ticket details</p>
                  <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-1 text-[13px]">
                    {Object.entries(r.extra).map(([k, v]) => (
                      <div key={k} className="contents"><dt className="text-subtle">{k}</dt><dd className="text-fg">{v}</dd></div>
                    ))}
                  </dl>
                </div>
              )}
              {r.related_ids?.length > 0 && <p className="text-xs text-subtle">Related records: {r.related_ids.join(', ')}</p>}
            </>
          )}
        </div>
      </aside>
    </div>
  )
}

import { useContext, useEffect, useState } from 'react'
import { BadgeCheck, Library, Search, Trash2 } from 'lucide-react'
import { api } from '../api'
import PageHeader from './PageHeader'
import { useToast } from './Toast'
import { Badge, Empty, formatTs, inputCls, outcomeTone, RecordContext, Skeleton } from './ui'

const SOURCES = [['', 'All records'], ['dataset', 'Past changes'], ['learning', 'Verified lessons']]

function Chip({ active, onClick, children }) {
  return (
    <button onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${active ? 'border-accent/60 bg-accent/12 text-fg' : 'border-line bg-surface text-muted hover:text-fg'}`}>
      {children}
    </button>
  )
}

export default function KnowledgeBase({ onChanged }) {
  const [rows, setRows] = useState(null)
  const [q, setQ] = useState('')
  const [source, setSource] = useState('')
  const [problemsOnly, setProblemsOnly] = useState(true)
  const { open } = useContext(RecordContext)
  const toast = useToast()
  const [confirmId, setConfirmId] = useState(null) // row asking "Delete?"
  const [busyId, setBusyId] = useState(null)
  const [reload, setReload] = useState(0)

  const remove = async (id) => {
    setBusyId(id)
    try {
      await api.deleteCase(id)
      setRows((cur) => cur.filter((r) => r.id !== id))
      toast.push({ tone: 'ok', title: `${id} deleted`, body: 'The lesson is removed from the knowledge base and from search.' })
      setReload((n) => n + 1)
      onChanged?.()
    } catch (e) {
      toast.push({ tone: 'bad', title: 'Could not delete', body: e.message })
    } finally {
      setBusyId(null)
      setConfirmId(null)
    }
  }

  useEffect(() => {
    const t = setTimeout(() => {
      const params = { limit: 300, problems_only: problemsOnly }
      if (q) params.q = q
      if (source) params.source = source
      api.cases(params).then(setRows).catch(() => setRows([]))
    }, 200)
    return () => clearTimeout(t)
  }, [q, source, problemsOnly, reload])

  return (
    <div>
      <PageHeader id="kb" icon={Library} eyebrow="Explore" title="Knowledge base"
        purpose="Every past change and every lesson saved by engineers: the memory the agent searches. Click a row to read the full record. Saved lessons can be deleted with the bin icon; official tickets cannot." />
      <section className="rounded-xl border border-line bg-surface shadow-card">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <div className="relative min-w-60 flex-1">
            <Search size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-subtle" />
            <input className={`${inputCls} pl-9`} placeholder="Search any word: node, error, MOP, root cause…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="flex flex-wrap gap-2">
            {SOURCES.map(([v, label]) => <Chip key={v} active={source === v} onClick={() => setSource(v)}>{label}</Chip>)}
            <Chip active={problemsOnly} onClick={() => setProblemsOnly(!problemsOnly)}>Only changes with a problem</Chip>
          </div>
          <span className="text-xs text-subtle">{rows ? `${rows.length} records` : ''}</span>
        </div>
        <div className="scroll-thin max-h-[calc(100vh-300px)] overflow-auto">
          {!rows && <div className="space-y-2 p-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-9" />)}</div>}
          {rows && !rows.length && <Empty icon={Search} title="No records found">Try another word or remove a filter.</Empty>}
          {rows && rows.length > 0 && (
            <table className="w-full text-left text-[13px]">
              <thead className="sticky top-0 z-10 bg-surface-2 text-xs text-subtle">
                <tr>{['ID', 'Date', 'Node', 'Type', 'MOP', 'Title', 'Outcome', ''].map((h, i) => <th key={i} className="px-4 py-2.5 font-semibold">{h}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} onClick={() => open(r.id)} className="cursor-pointer border-t border-line transition hover:bg-surface-2">
                    <td className="px-4 py-2.5 font-mono text-xs font-semibold whitespace-nowrap text-link">{r.id}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-subtle" title={r.verified_at || r.date}>{r.verified_at ? formatTs(r.verified_at) : r.date}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-fg">{r.node}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-muted">{r.node_type}</td>
                    <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap text-subtle">{r.mop_id}{r.mop_step && ` · ${r.mop_step}`}</td>
                    <td className="max-w-md px-4 py-2.5 text-fg">
                      <span className="line-clamp-1">{r.title}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="flex gap-1">
                        {r.outcome && <Badge tone={outcomeTone(r.outcome)}>{r.outcome}</Badge>}
                        {r.source === 'learning' && <Badge tone="ok" icon={BadgeCheck}>verified</Badge>}
                      </span>
                    </td>
                    <td className="w-px px-3 py-1.5 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                      {r.source === 'learning' && (confirmId === r.id ? (
                        <span className="flex items-center gap-1.5 text-xs">
                          <span className="text-muted">Delete?</span>
                          <button disabled={busyId === r.id} onClick={() => remove(r.id)}
                            className="rounded-md bg-bad px-2 py-1 font-semibold text-white transition hover:opacity-90 disabled:opacity-60">
                            {busyId === r.id ? 'Deleting…' : 'Yes'}
                          </button>
                          <button onClick={() => setConfirmId(null)}
                            className="rounded-md border border-line px-2 py-1 font-medium text-muted transition hover:text-fg">No</button>
                        </span>
                      ) : (
                        <button title="Delete this saved lesson" aria-label={`Delete ${r.id}`} onClick={() => setConfirmId(r.id)}
                          className="rounded-md p-1.5 text-subtle transition hover:bg-bad/10 hover:text-bad">
                          <Trash2 size={15} />
                        </button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  )
}

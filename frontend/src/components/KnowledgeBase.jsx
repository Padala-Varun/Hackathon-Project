import { useContext, useEffect, useState } from 'react'
import { api } from '../api'
import { Card, inputCls, Pill, RecordContext } from './ui'

export default function KnowledgeBase() {
  const [rows, setRows] = useState([])
  const [q, setQ] = useState('')
  const [source, setSource] = useState('')
  const [problemsOnly, setProblemsOnly] = useState(true)
  const { open } = useContext(RecordContext)

  useEffect(() => {
    const t = setTimeout(() => {
      const params = { limit: 300, problems_only: problemsOnly }
      if (q) params.q = q
      if (source) params.source = source
      api.cases(params).then(setRows).catch(() => {})
    }, 200)
    return () => clearTimeout(t)
  }, [q, source, problemsOnly])

  return (
    <Card title={`Institutional memory · ${rows.length} records`}>
      <div className="mb-3 flex flex-wrap gap-2">
        <input className={`${inputCls} max-w-sm`} placeholder="filter (any field)…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className={`${inputCls} w-48`} value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">all sources</option>
          <option value="dataset">LNI history (dataset)</option>
          <option value="learning">verified learnings</option>
        </select>
        <label className="flex items-center gap-2 text-xs text-ink-300">
          <input type="checkbox" checked={problemsOnly} onChange={(e) => setProblemsOnly(e.target.checked)} /> only LNIs with a problem
        </label>
      </div>
      <div className="scroll-thin max-h-[65vh] overflow-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-ink-900 text-ink-500">
            <tr>{['ID', 'Date', 'Node', 'Type', 'MOP', 'Title', 'Outcome', ''].map((h) => <th key={h} className="px-2 py-2 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} onClick={() => open(r.id)} className="cursor-pointer border-t border-ink-800 hover:bg-ink-850">
                <td className="px-2 py-1.5 font-mono text-info">{r.id}</td>
                <td className="px-2 py-1.5 font-mono text-ink-500">{r.date}</td>
                <td className="px-2 py-1.5 font-mono">{r.node}</td>
                <td className="px-2 py-1.5 text-ink-300">{r.node_type}</td>
                <td className="px-2 py-1.5 font-mono text-ink-500">{r.mop_id}{r.mop_step && ` #${r.mop_step}`}</td>
                <td className="max-w-md truncate px-2 py-1.5 text-ink-100">{r.title}</td>
                <td className="px-2 py-1.5 text-ink-300">{r.outcome}</td>
                <td className="px-2 py-1.5">{r.source === 'learning' && <Pill tone="ok">verified</Pill>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

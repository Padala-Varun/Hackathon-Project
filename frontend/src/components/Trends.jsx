import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, Cite, Empty, Pill, Spinner } from './ui'

const OUTCOME_TONE = { Outage: 'bad', Rollback: 'bad', 'Service degraded': 'warn', Resolved: 'ok', Success: 'dim' }

/** Single-series horizontal bars: label | bar | value. Hover shows a tooltip with the detail. */
function HBars({ rows, max }) {
  const [hover, setHover] = useState(null)
  return (
    <ul className="space-y-1.5">
      {rows.map((r, i) => (
        <li key={r.label} className="relative grid grid-cols-[minmax(0,300px)_1fr_32px] items-center gap-2 rounded px-1 py-0.5 hover:bg-ink-850"
          onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
          <span className="truncate text-xs text-ink-300" title={r.label}>{r.label}</span>
          <div className="h-3 rounded-r bg-ink-800/40">
            <div className="h-full rounded-r bg-amber" style={{ width: `${(100 * r.value) / max}%`, opacity: hover === null || hover === i ? 1 : 0.45 }} />
          </div>
          <span className="text-right font-mono text-xs text-ink-100">{r.value}</span>
          {hover === i && r.tip && (
            <div className="pointer-events-none absolute left-1/3 top-full z-10 mt-1 rounded-md border border-ink-700 bg-ink-950 px-2 py-1 text-[11px] text-ink-300 shadow-lg">{r.tip}</div>
          )}
        </li>
      ))}
    </ul>
  )
}

function MonthColumns({ data }) {
  const [hover, setHover] = useState(null)
  const entries = Object.entries(data)
  const max = Math.max(1, ...entries.map(([, v]) => v))
  return (
    <div>
      <div className="flex h-36 items-end gap-0.5 border-b border-ink-700">
        {entries.map(([m, v], i) => (
          <div key={m} className="relative flex h-full flex-1 items-end" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <div className="w-full rounded-t bg-amber" style={{ height: `${(100 * v) / max}%`, opacity: hover === null || hover === i ? 1 : 0.45 }} />
            {hover === i && (
              <div className="pointer-events-none absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-ink-700 bg-ink-950 px-2 py-0.5 text-[11px] text-ink-100">
                {m}: {v} problem LNIs
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-0.5">
        {entries.map(([m]) => <span key={m} className="flex-1 text-center font-mono text-[10px] text-ink-500">{m.slice(5)}</span>)}
      </div>
    </div>
  )
}

export default function Trends() {
  const [t, setT] = useState(null)
  const [digest, setDigest] = useState(null)
  useEffect(() => {
    api.trends().then(setT).catch(() => {})
    api.digest(30).then(setDigest).catch(() => {})
  }, [])
  if (!t) return <p className="flex items-center gap-2 text-sm text-ink-500"><Spinner /> loading trends…</p>

  const maxRec = Math.max(1, ...t.recurring.map((r) => r.count))
  const nodeRows = Object.entries(t.by_node_type).map(([label, value]) => ({ label, value }))
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        {[['LNI records', t.total_records], ['With a problem', t.problem_records], ['Recurring problems', t.recurring.length],
          ['Repeat occurrences', t.recurring.reduce((s, r) => s + r.count - 1, 0)]].map(([k, v]) => (
          <div key={k} className="rounded-xl border border-ink-700 bg-ink-900 px-4 py-3">
            <p className="text-2xl font-bold text-ink-100">{v}</p>
            <p className="text-xs text-ink-500">{k}</p>
          </div>
        ))}
      </div>
      <Card title="Repeat failures · same root cause seen more than once">
        {t.recurring.length ? (
          <HBars max={maxRec} rows={t.recurring.map((r) => ({
            label: r.title, value: r.count,
            tip: `${r.node_type} · ${r.nodes.join(', ')} · first ${r.first_seen}, last ${r.last_seen} · ${r.ids.join(', ')}`,
          }))} />
        ) : <Empty>No recurring problems detected.</Empty>}
      </Card>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Problem LNIs by node type"><HBars rows={nodeRows} max={Math.max(1, ...nodeRows.map((r) => r.value))} /></Card>
        <Card title="Problem LNIs per month"><MonthColumns data={t.by_month} /></Card>
      </div>
      <Card title="Outcomes of problem LNIs">
        <div className="flex flex-wrap gap-2">
          {Object.entries(t.by_outcome).map(([k, v]) => <Pill key={k} tone={OUTCOME_TONE[k] || 'dim'}>{k}: <b>{v}</b></Pill>)}
        </div>
      </Card>
      {digest && (
        <Card title={`Digest · top recurring issues ${digest.start} → ${digest.end}`}>
          <ol className="space-y-2 text-[13px] leading-relaxed text-ink-100">
            {digest.markdown.split('\n').filter((l) => /^\d+\./.test(l)).map((l, i) => {
              const ids = (l.match(/\[([^\]]+)\]$/) || [])[1]
              const body = l.replace(/^\d+\.\s*/, '').replace(/\s*\[[^\]]+\]$/, '').replace(/\*\*/g, '')
              return <li key={i}>{i + 1}. {body} {ids?.split(', ').map((id) => <Cite key={id} id={id} />)}</li>
            })}
          </ol>
        </Card>
      )}
    </div>
  )
}

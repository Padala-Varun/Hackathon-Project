import { useEffect, useState } from 'react'
import { CalendarRange, Database, Newspaper, Repeat, TrendingUp, TriangleAlert } from 'lucide-react'
import { api } from '../api'
import PageHeader from './PageHeader'
import { Badge, Card, Cite, outcomeTone, Skeleton } from './ui'

/** Single-series horizontal bars: label | bar | value. Hover shows a tooltip with the detail. */
function HBars({ rows, max, labelWidth = 300 }) {
  const [hover, setHover] = useState(null)
  return (
    <ul className="space-y-1">
      {rows.map((r, i) => (
        <li key={r.label} className="relative grid items-center gap-3 rounded-md px-2 py-1 hover:bg-surface-2"
          style={{ gridTemplateColumns: `minmax(0,${labelWidth}px) 1fr 28px` }}
          onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
          <span className="truncate text-[13px] text-muted" title={r.label}>{r.label}</span>
          <div className="h-3 rounded-r bg-surface-3">
            <div className="h-full rounded-r bg-chart transition-all duration-500" style={{ width: `${(100 * r.value) / max}%`, opacity: hover === null || hover === i ? 1 : 0.45 }} />
          </div>
          <span className="text-right text-[13px] font-semibold text-fg">{r.value}</span>
          {hover === i && r.tip && (
            <div className="pointer-events-none absolute top-full left-1/3 z-20 mt-1 max-w-md rounded-lg border border-line bg-surface px-3 py-2 text-xs text-muted shadow-pop">{r.tip}</div>
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
      <div className="flex h-44 items-end gap-1.5 border-b border-line">
        {entries.map(([m, v], i) => (
          <div key={m} className="relative flex h-full flex-1 items-end" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <div className="w-full rounded-t bg-chart transition-all duration-500" style={{ height: `${(100 * v) / max}%`, opacity: hover === null || hover === i ? 1 : 0.45 }} />
            {hover === i && (
              <div className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 rounded-md border border-line bg-surface px-2 py-1 text-xs whitespace-nowrap text-fg shadow-pop">
                {m}: <b>{v}</b> problem changes
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex gap-1.5">
        {entries.map(([m]) => <span key={m} className="flex-1 text-center text-[11px] text-subtle">{m.slice(5)}/{m.slice(2, 4)}</span>)}
      </div>
    </div>
  )
}

function Stat({ icon: Icon, value, label }) {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-line bg-surface p-4 shadow-card">
      <div className="rounded-lg bg-accent/12 p-2.5 text-accent-ink"><Icon size={20} /></div>
      <div><p className="text-2xl leading-tight font-bold text-fg">{value}</p><p className="text-xs text-subtle">{label}</p></div>
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

  const header = (
    <PageHeader id="trends" icon={TrendingUp} eyebrow="Explore" title="Trends"
      purpose="Which problems keep coming back, on which kinds of equipment, and when. Repeat failures are the best candidates for a permanent fix." />
  )
  if (!t) return <div>{header}<div className="grid gap-4 sm:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20" />)}</div></div>

  const maxRec = Math.max(1, ...t.recurring.map((r) => r.count))
  const nodeRows = Object.entries(t.by_node_type).map(([label, value]) => ({ label, value }))
  return (
    <div className="space-y-5">
      {header}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Database} value={t.total_records} label="past changes in memory" />
        <Stat icon={TriangleAlert} value={t.problem_records} label="changes that had a problem" />
        <Stat icon={Repeat} value={t.recurring.length} label="problems that repeat" />
        <Stat icon={CalendarRange} value={t.recurring.reduce((s, r) => s + r.count - 1, 0)} label="times a known problem came back" />
      </div>
      <Card title="Repeat failures" icon={Repeat} subtitle="Same root cause seen more than once, even when written differently. Hover a bar for details.">
        <HBars max={maxRec} rows={t.recurring.map((r) => ({
          label: r.title, value: r.count,
          tip: `${r.node_type} · ${r.nodes.join(', ')} · first ${r.first_seen}, last ${r.last_seen} · ${r.ids.join(', ')}`,
        }))} />
      </Card>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Problem changes by equipment type" icon={Database}>
          <HBars rows={nodeRows} max={Math.max(1, ...nodeRows.map((r) => r.value))} labelWidth={130} />
        </Card>
        <Card title="Problem changes per month" icon={CalendarRange}><MonthColumns data={t.by_month} /></Card>
      </div>
      <Card title="How problem changes ended" icon={TriangleAlert}>
        <div className="flex flex-wrap gap-2">
          {Object.entries(t.by_outcome).map(([k, v]) => <Badge key={k} tone={outcomeTone(k)} className="!px-2.5 !py-1 !text-xs">{k}: <b>{v}</b></Badge>)}
        </div>
      </Card>
      {digest && (
        <Card title="Digest: top recurring issues" icon={Newspaper} subtitle={`${digest.start} → ${digest.end}`}>
          <ol className="space-y-3">
            {digest.markdown.split('\n').filter((l) => /^\d+\./.test(l)).map((l, i) => {
              const ids = (l.match(/\[([^\]]+)\]$/) || [])[1]
              const body = l.replace(/^\d+\.\s*/, '').replace(/\s*\[[^\]]+\]$/, '').replace(/\*\*/g, '')
              return (
                <li key={i} className="flex gap-3 text-sm text-fg">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-3 text-xs font-bold text-muted">{i + 1}</span>
                  <span>{body} {ids?.split(', ').map((id) => <Cite key={id} id={id} />)}</span>
                </li>
              )
            })}
          </ol>
        </Card>
      )}
    </div>
  )
}

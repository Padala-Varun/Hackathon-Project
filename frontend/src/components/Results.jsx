import { useState } from 'react'
import { Button, Card, Cite, Cited, ConfidenceBar, Pill, Spinner } from './ui'

const OUTCOME_TONE = { outage: 'bad', rollback: 'bad', 'service degraded': 'warn', resolved: 'ok' }

export function MatchCard({ m, rank, onWorked, onWriteBack }) {
  const [open, setOpen] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  return (
    <article className="rounded-xl border border-ink-700 bg-ink-850 p-3.5">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-ink-500">#{rank}</span>
        <Cite id={m.record_id} />
        {m.duplicates.map((d) => <Cite key={d.record_id} id={d.record_id} />)}
        {m.duplicates.length > 0 && <Pill tone="amber">seen {m.duplicates.length + 1}×</Pill>}
        {m.source === 'learning' && <Pill tone="ok">✓ verified learning</Pill>}
        {m.success_count > 0 && <Pill tone="ok">fix confirmed {m.success_count}×</Pill>}
        {m.outcome && <Pill tone={OUTCOME_TONE[m.outcome.toLowerCase()] || 'dim'}>{m.outcome}</Pill>}
        <span className="ml-auto font-mono text-[11px] text-ink-500">
          {[m.node, m.release && `rel ${m.release}`, m.mop_id && `${m.mop_id}${m.mop_step ? ` step ${m.mop_step}` : ''}`, m.date].filter(Boolean).join(' · ')}
        </span>
      </div>
      <h4 className="mb-2 text-sm font-semibold text-ink-100">{m.title}</h4>
      <ConfidenceBar value={m.confidence} />
      <dl className="mt-3 space-y-1.5 text-[13px] leading-relaxed">
        <div><dt className="inline font-semibold text-ink-300">Root cause: </dt><dd className="inline text-ink-100">{m.root_cause}</dd></div>
        {m.resolution && <div><dt className="inline font-semibold text-ink-300">Fix: </dt><dd className="inline text-ink-100">{m.resolution}</dd></div>}
        {m.learning && <div><dt className="inline font-semibold text-ink-300">Learning: </dt><dd className="inline text-ink-100">{m.learning}</dd></div>}
      </dl>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button onClick={() => setOpen(!open)} className="text-xs text-ink-500 hover:text-ink-300">
          {open ? '▾' : '▸'} why this match
        </button>
        <span className="flex-1" />
        {onWorked && (
          <Button variant="ok" className="!px-2.5 !py-1 text-xs" disabled={confirmed}
            onClick={async () => { await onWorked(m); setConfirmed(true) }}>
            {confirmed ? '✓ confirmed' : 'This fix worked'}
          </Button>
        )}
        {onWriteBack && <Button variant="ghost" className="!px-2.5 !py-1 text-xs" onClick={() => onWriteBack(m)}>Write back learning →</Button>}
      </div>
      {open && (
        <div className="mt-2 space-y-1.5 rounded-lg border border-ink-800 bg-ink-950/60 p-2.5 text-xs text-ink-300">
          {m.reasons.map((r, i) => <div key={i}>• {r}</div>)}
          {m.evidence.map((e) => (
            <div key={e.chunk_id} className="border-l-2 border-info/40 pl-2 text-ink-500">
              <span className="font-mono text-[10px] uppercase text-info">{e.field.replace('_', ' ')}</span> {e.text}
            </div>
          ))}
        </div>
      )}
    </article>
  )
}

export function RecommendationPanel({ result, llmText, running, mode }) {
  const streaming = running && llmText
  const status = result?.status
  return (
    <Card title={mode === 'pre_change' ? 'Agent recommendation · before the change' : 'Agent recommendation · during the incident'} accent
      right={result && (result.llm_used ? <Pill tone="info">LLM-drafted · citation-checked</Pill> : status === 'ok' ? <Pill tone="dim">deterministic cited draft</Pill> : null)}>
      {!result && !running && <p className="text-sm text-ink-500">No recommendation yet.</p>}
      {running && !llmText && !result && <p className="flex items-center gap-2 text-sm text-ink-300"><Spinner /> Agent is working…</p>}
      {streaming && !result && <pre className="caret whitespace-pre-wrap font-sans text-sm leading-relaxed text-ink-100">{llmText}</pre>}
      {status === 'no_match' && (
        <div className="rounded-lg border border-warn/40 bg-warn/5 p-3 text-sm text-warn">{result.summary}</div>
      )}
      {status === 'ok' && (
        <ul className="space-y-2">
          {result.summary.split('\n').filter(Boolean).map((line, i) => (
            <li key={i} className="text-sm leading-relaxed text-ink-100"><Cited text={line.replace(/^[-*]\s*/, '• ')} /></li>
          ))}
        </ul>
      )}
      {result?.dropped_claims?.length > 0 && (
        <details className="mt-3 text-xs text-ink-500">
          <summary className="cursor-pointer">Guardrail removed {result.dropped_claims.length} uncited statement(s)</summary>
          <ul className="mt-1 list-disc pl-5">{result.dropped_claims.map((d, i) => <li key={i} className="line-through">{d}</li>)}</ul>
        </details>
      )}
      {result && <p className="mt-3 border-t border-ink-800 pt-2 text-[11px] italic text-ink-500">The agent never executes changes. Review the cited records and decide.</p>}
    </Card>
  )
}

export function ClarifyCard({ clarification, onAnswer, blocking }) {
  const [custom, setCustom] = useState('')
  return (
    <div className={`rounded-xl border p-4 ${blocking ? 'border-amber/60 bg-amber/5' : 'border-ink-700 bg-ink-900'}`}>
      <p className="mb-1 font-mono text-[11px] font-semibold uppercase tracking-wider text-amber">Agent asks</p>
      <p className="mb-3 text-sm text-ink-100">{clarification.question}</p>
      <div className="flex flex-wrap gap-2">
        {clarification.options.map((o) => (
          <Button key={o} variant="ghost" className="!py-1 font-mono text-xs" onClick={() => onAnswer(clarification.field, o)}>{o}</Button>
        ))}
        <input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="other…"
          className="w-28 rounded-lg border border-ink-700 bg-ink-950 px-2 py-1 text-xs" />
        {custom && <Button variant="ghost" className="!py-1 text-xs" onClick={() => onAnswer(clarification.field, custom)}>use</Button>}
        {blocking && <Button variant="ghost" className="!py-1 text-xs text-ink-500" onClick={() => onAnswer(null, null)}>skip</Button>}
      </div>
    </div>
  )
}

const RISK_STYLE = { High: 'text-bad border-bad/50 bg-bad/10', Medium: 'text-warn border-warn/50 bg-warn/10', Low: 'text-ok border-ok/50 bg-ok/10' }

export function RiskPanel({ risk, notification }) {
  return (
    <Card title="Pre-change risk score">
      <div className="flex items-start gap-4">
        <div className={`flex h-20 w-20 shrink-0 flex-col items-center justify-center rounded-xl border ${RISK_STYLE[risk.level]}`}>
          <span className="text-2xl font-bold">{risk.score}</span>
          <span className="text-[10px] font-semibold uppercase tracking-wider">{risk.level}</span>
        </div>
        <ul className="space-y-1 text-xs text-ink-300">{risk.reasons.map((r, i) => <li key={i}>• <Cited text={r.replace(/^(\S+-\S+):/, '[$1]:')} /></li>)}</ul>
      </div>
      {notification && (
        <div className="mt-3 rounded-lg border border-amber/40 bg-amber/5 px-3 py-2 text-xs text-amber">
          🔔 High-risk alert sent to {notification.result?.target} (Teams card)
        </div>
      )}
    </Card>
  )
}

export function MopSteps({ mopId, steps }) {
  if (!steps?.length) return null
  return (
    <Card title={`${mopId} · step-by-step pitfalls`}>
      <ol className="space-y-2">
        {steps.map((s) => (
          <li key={s.no} className={`flex gap-3 rounded-lg px-2 py-1.5 ${s.warnings.length ? 'bg-bad/5' : ''}`}>
            <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px] ${s.warnings.length ? 'bg-bad text-ink-950' : 'bg-ink-800 text-ink-300'}`}>{s.no}</span>
            <div className="text-[13px]">
              <p className={s.warnings.length ? 'text-ink-100' : 'text-ink-500'}>{s.text}</p>
              {s.warnings.map((w, i) => (
                <p key={i} className="mt-1 text-xs text-bad">⚠ {w.text} {w.citations.map((c) => <Cite key={c} id={c} />)} <span className="font-mono text-[10px] text-ink-500">{w.confidence}%</span></p>
              ))}
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}

export function Checklist({ title, items }) {
  if (!items?.length) return null
  return (
    <Card title={title}>
      <ul className="space-y-2">
        {items.map((it, i) => (
          <li key={i} className="flex gap-2 text-[13px] leading-relaxed text-ink-100">
            <span className="mt-0.5 text-ok">☐</span>
            <span>{it.text} {it.citations.map((c) => <Cite key={c} id={c} />)}
              {!it.citations.length && <Pill tone="dim">general practice · not from history</Pill>}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function NodeHistory({ history, node }) {
  if (!history?.length) return null
  return (
    <Card title={`Node history · ${node}`}>
      <ul className="space-y-1.5 text-xs">
        {history.map((h) => (
          <li key={h.id} className="flex items-center gap-2">
            <Cite id={h.id} /><span className="font-mono text-ink-500">{h.date}</span>
            <span className="flex-1 truncate text-ink-300">{h.title}</span>
            <Pill tone={OUTCOME_TONE[h.outcome?.toLowerCase()] || 'dim'}>{h.outcome || '—'}</Pill>
          </li>
        ))}
      </ul>
    </Card>
  )
}

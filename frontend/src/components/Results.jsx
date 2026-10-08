import { useState } from 'react'
import {
  BadgeCheck, BellRing, Bot, ChevronDown, CircleCheck, FileText, GitFork, History, ListChecks, ScanSearch,
  SearchX, Sparkles, Square, SquareCheck, Target, TriangleAlert, Wrench,
} from 'lucide-react'
import {
  Badge, Button, Card, Cite, Cited, ConfidenceRing, confTone, confWord, Empty, formatTs, Segmented, Skeleton, outcomeTone,
} from './ui'

const TONE_BOX = {
  ok: 'border-ok/30 bg-ok/8', warn: 'border-warn/30 bg-warn/8', bad: 'border-bad/30 bg-bad/8', neutral: 'border-line bg-surface',
}
const TONE_TEXT = { ok: 'text-ok', warn: 'text-warn', bad: 'text-bad', neutral: 'text-fg' }
const RISK_TONE = { High: 'bad', Medium: 'warn', Low: 'ok' }

/* ------------------------------------------------------------------ verdict */
export function VerdictBanner({ result, mode }) {
  const [why, setWhy] = useState(false)
  if (result.status === 'no_match') {
    return (
      <div className={`animate-fade-up rounded-xl border p-5 ${TONE_BOX.warn}`}>
        <div className="flex gap-4">
          <div className="rounded-full bg-warn/15 p-2.5 text-warn"><SearchX size={22} /></div>
          <div>
            <p className="text-lg font-semibold text-fg">No verified match found</p>
            <p className="mt-1 text-sm text-muted">
              Nothing in the history is similar enough (above 50% match), so the agent does <b>not</b> suggest a fix and does not guess.
              Escalate as usual. Closest candidates are listed below for reference only.
            </p>
          </div>
        </div>
      </div>
    )
  }
  if (mode === 'pre_change' && result.risk) {
    const tone = RISK_TONE[result.risk.level]
    const pitfalls = result.items.filter((i) => i.kind === 'pitfall').length
    const flagged = result.mop_steps.filter((s) => s.warnings.length).map((s) => s.no)
    return (
      <div className={`animate-fade-up rounded-xl border p-5 ${TONE_BOX[tone]}`}>
        <div className="flex flex-wrap items-center gap-5">
          <div className={`flex h-20 w-20 shrink-0 flex-col items-center justify-center rounded-2xl border-2 bg-surface ${TONE_TEXT[tone]}`} style={{ borderColor: 'currentColor' }}>
            <span className="text-3xl leading-none font-bold">{result.risk.score}</span>
            <span className="mt-1 text-[10px] font-bold tracking-wider uppercase">risk</span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-lg font-semibold text-fg">
              <span className={TONE_TEXT[tone]}>{result.risk.level} risk</span> · {pitfalls} known pitfall{pitfalls === 1 ? '' : 's'} found in similar past changes
            </p>
            <p className="mt-1 text-sm text-muted">Review the recommendation and tick the check-list below before you start. The agent never makes the change itself.</p>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {flagged.length > 0 && <Badge tone="bad" icon={TriangleAlert}>Risky MOP steps: {flagged.join(', ')}</Badge>}
              {result.node_history?.length > 0 && <Badge icon={History}>{result.node_history.length} past change(s) on this node</Badge>}
              {result.notification && <Badge tone="warn" icon={BellRing}>High-risk alert sent to the team</Badge>}
              <button onClick={() => setWhy(!why)} className="inline-flex items-center gap-1 text-xs font-semibold text-link hover:underline">
                Why this score? <ChevronDown size={13} className={`transition-transform ${why ? 'rotate-180' : ''}`} />
              </button>
            </div>
          </div>
        </div>
        <div className="reveal" data-open={why}>
          <div>
            <ul className="mt-4 space-y-1 border-t border-line pt-3 text-[13px] text-muted">
              {result.risk.reasons.map((r, i) => <li key={i}>• <Cited text={r.replace(/^(\S+-\S+):/, '[$1]:')} /></li>)}
            </ul>
          </div>
        </div>
      </div>
    )
  }
  const top = result.matches[0]
  const tone = confTone(top.confidence)
  return (
    <div className={`animate-fade-up rounded-xl border p-5 ${TONE_BOX[tone]}`}>
      <div className="flex items-center gap-5">
        <ConfidenceRing value={top.confidence} size={72} />
        <div className="min-w-0 flex-1">
          <p className="text-lg font-semibold text-fg">
            Most likely cause found · <span className={TONE_TEXT[tone]}>{confWord(top.confidence).toLowerCase()}</span>
            {top.duplicates.length > 0 && <span className="text-muted"> · seen {top.duplicates.length + 1}× before</span>}
          </p>
          <p className="mt-1 line-clamp-2 text-sm text-muted">{top.root_cause || top.title}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1">
            <span className="text-xs text-subtle">Proof:</span>
            {[top.record_id, ...top.duplicates.map((d) => d.record_id)].map((id) => <Cite key={id} id={id} />)}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ recommendation */
const KIND = {
  pitfall: [TriangleAlert, 'text-warn'],
  cause: [Target, 'text-bad'],
  fix: [Wrench, 'text-ok'],
  alternative: [GitFork, 'text-muted'],
  precheck: [CircleCheck, 'text-link'],
}

function ItemLine({ item }) {
  const [Icon, color] = KIND[item.kind] || [CircleCheck, 'text-link']
  const m = item.text.match(/^([^:(]{3,40}?)(?: \(([^)]*)\))?: (.*)$/s)
  const label = m ? m[1] : item.kind === 'precheck' ? 'Check' : null
  const meta = m ? m[2] : null
  const body = m ? m[3] : item.text
  return (
    <li className="flex gap-3">
      <Icon size={17} className={`mt-0.5 shrink-0 ${color}`} />
      <p className="text-sm leading-relaxed text-fg">
        {label && <b className="font-semibold">{label}</b>}
        {meta && <span className="text-subtle"> ({meta})</span>}
        {label && ': '}
        {body} {item.citations.map((c) => <Cite key={c} id={c} />)}
      </p>
    </li>
  )
}

export function Recommendation({ result, llmText, running }) {
  if (result?.status === 'no_match') return null // the verdict banner already says "No verified match found"
  const streaming = running && llmText && !result
  const badge = result?.status === 'ok' && (result.llm_used
    ? <Badge tone="link" icon={Sparkles}>Written by AI · every line checked</Badge>
    : <Badge icon={FileText}>Built from past records</Badge>)
  return (
    <Card title="What the agent recommends" icon={Bot} right={badge} className="animate-fade-up">
      {streaming && <pre className="caret font-sans text-sm leading-relaxed whitespace-pre-wrap text-fg">{llmText}</pre>}
      {result?.status === 'ok' && (
        <ul className="space-y-3">
          {result.llm_used
            ? result.summary.split('\n').filter(Boolean).map((line, i) => (
              <li key={i} className="flex gap-3"><Sparkles size={16} className="mt-0.5 shrink-0 text-link" />
                <p className="text-sm leading-relaxed text-fg"><Cited text={line.replace(/^[-*•]\s*/, '')} /></p></li>
            ))
            : [...result.items, ...result.prechecks.slice(0, 3)].map((it, i) => <ItemLine key={i} item={it} />)}
        </ul>
      )}
      {result?.status === 'no_match' && <p className="text-sm text-muted">{result.summary}</p>}
      {result?.dropped_claims?.length > 0 && (
        <details className="mt-4 text-xs text-subtle">
          <summary className="cursor-pointer font-medium">Safety check removed {result.dropped_claims.length} AI sentence(s) that had no proof</summary>
          <ul className="mt-1.5 list-disc pl-5">{result.dropped_claims.map((d, i) => <li key={i} className="line-through">{d}</li>)}</ul>
        </details>
      )}
      {result && (
        <p className="mt-4 flex items-center gap-1.5 border-t border-line pt-3 text-xs text-subtle">
          <BadgeCheck size={14} /> Every line links to the past record it comes from. Click an ID to see the proof. The engineer decides.
        </p>
      )}
    </Card>
  )
}

/* -------------------------------------------------------------- clarification */
export function ClarifyCard({ clarification, onAnswer, blocking }) {
  const [custom, setCustom] = useState('')
  return (
    <div className={`animate-fade-up rounded-xl border p-5 ${blocking ? 'border-accent/50 bg-accent/8' : 'border-line bg-surface shadow-card'}`}>
      <div className="flex gap-3">
        <div className="h-fit rounded-full bg-accent/20 p-2 text-accent-ink"><Bot size={18} /></div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold tracking-wide text-accent-ink uppercase">{blocking ? 'The agent needs one detail' : 'Optional: help the agent refine'}</p>
          <p className="mt-0.5 text-[15px] font-medium text-fg">{clarification.question.replace(' (searching anyway; answer to refine)', '')}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {clarification.options.map((o) => (
              <Button key={o} variant="secondary" size="sm" className="font-mono" onClick={() => onAnswer(clarification.field, o)}>{o}</Button>
            ))}
            <input value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="Other…"
              onKeyDown={(e) => e.key === 'Enter' && custom && onAnswer(clarification.field, custom)}
              className="h-8 w-28 rounded-lg border border-line-strong bg-surface px-2.5 text-xs text-fg" />
            {custom && <Button size="sm" onClick={() => onAnswer(clarification.field, custom)}>Use</Button>}
            {blocking && <Button variant="ghost" size="sm" onClick={() => onAnswer(null, null)}>Skip this question</Button>}
          </div>
        </div>
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- detail tabs */
export function DetailTabs({ tabs }) {
  const visible = tabs.filter((t) => t.show !== false)
  const [active, setActive] = useState(visible[0]?.id)
  const current = visible.find((t) => t.id === active) || visible[0]
  if (!current) return null
  return (
    <div className="animate-fade-up space-y-4" style={{ animationDelay: '80ms' }}>
      <Segmented tabs={visible} value={current.id} onChange={setActive} />
      <div key={current.id} className="animate-fade-in">{current.content}</div>
    </div>
  )
}

export function Checklist({ items }) {
  const [done, setDone] = useState({})
  if (!items?.length) return <Empty icon={ListChecks} title="No check-list">No checks were found for this case.</Empty>
  const count = items.filter((_, i) => done[i]).length
  return (
    <Card title="Check-list from past lessons" icon={ListChecks}
      right={<span className="text-xs font-medium text-subtle">{count} of {items.length} done</span>}>
      <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div className="h-full rounded-full bg-ok transition-all duration-500" style={{ width: `${(100 * count) / items.length}%` }} />
      </div>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i}>
            <div role="checkbox" aria-checked={!!done[i]} tabIndex={0}
              onClick={() => setDone({ ...done, [i]: !done[i] })}
              onKeyDown={(e) => { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); setDone({ ...done, [i]: !done[i] }) } }}
              className="flex w-full cursor-pointer gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-surface-2">
              {done[i] ? <SquareCheck size={18} className="mt-0.5 shrink-0 text-ok" /> : <Square size={18} className="mt-0.5 shrink-0 text-subtle" />}
              <span className={`text-sm leading-relaxed ${done[i] ? 'text-subtle line-through' : 'text-fg'}`}>
                {it.text} {it.citations.map((c) => <Cite key={c} id={c} />)}
                {!it.citations.length && <Badge className="ml-1">general practice · not from history</Badge>}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function MopSteps({ mopId, steps }) {
  if (!steps?.length) return <Empty icon={FileText} title="No MOP given">Add a MOP (e.g. MOP-UPG-04) to check every step for known pitfalls.</Empty>
  const flagged = steps.filter((s) => s.warnings.length).length
  return (
    <Card title={`${mopId}: step by step`} icon={FileText} subtitle={`${flagged} of ${steps.length} steps went wrong in past changes`}>
      <ol className="relative">
        {steps.map((s, i) => {
          const risky = s.warnings.length > 0
          return (
            <li key={s.no} className="relative flex gap-4 pb-5 last:pb-0">
              {i < steps.length - 1 && <span className="absolute top-8 bottom-0 left-[15px] w-px bg-line" />}
              <span className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${risky ? 'bg-bad text-white' : 'border border-line bg-surface-2 text-muted'}`}>
                {risky ? <TriangleAlert size={15} /> : s.no}
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <p className={`text-sm ${risky ? 'font-medium text-fg' : 'text-muted'}`}><span className="text-subtle">Step {s.no} · </span>{s.text}</p>
                {s.warnings.map((w, j) => (
                  <div key={j} className="mt-2 rounded-lg border border-bad/25 bg-bad/6 px-3 py-2 text-[13px] text-fg">
                    <b className="text-bad">Watch out:</b> {w.text} {w.citations.map((c) => <Cite key={c} id={c} />)}
                    <span className="ml-1 text-xs text-subtle">{w.confidence}% match</span>
                  </div>
                ))}
              </div>
            </li>
          )
        })}
      </ol>
    </Card>
  )
}

/* ---------------------------------------------------------------- match card */
/** Long procedures (commands, config) are folded: first lines shown, "Show full fix" expands. */
function LongText({ text, limit = 320 }) {
  const [open, setOpen] = useState(false)
  if (text.length <= limit) return <span className="whitespace-pre-line">{text}</span>
  return (
    <div>
      {open
        ? <pre className="scroll-thin max-h-96 overflow-auto rounded-lg bg-surface-2 p-3 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-fg">{text}</pre>
        : <span className="whitespace-pre-line">{text.slice(0, limit).replace(/\s+\S*$/, '')}…</span>}
      <button onClick={() => setOpen(!open)} className="mt-1 block text-xs font-semibold text-link hover:underline">
        {open ? 'Show less' : `Show full fix (${text.split('\n').length} lines)`}
      </button>
    </div>
  )
}

export function MatchCard({ m, rank, onWorked, onWriteBack }) {
  const [open, setOpen] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const tone = confTone(m.confidence)
  const meta = [m.node, m.release && `release ${m.release}`, m.mop_id && `${m.mop_id}${m.mop_step ? ` step ${m.mop_step}` : ''}`, m.date].filter(Boolean)
  return (
    <article className="lift rounded-xl border border-line bg-surface p-5 shadow-card">
      <div className="flex gap-4">
        <ConfidenceRing value={m.confidence} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold text-subtle">#{rank}</span>
            <Cite id={m.record_id} />
            {m.duplicates.map((d) => <Cite key={d.record_id} id={d.record_id} />)}
            {m.duplicates.length > 0 && <Badge tone="accent">seen {m.duplicates.length + 1}×</Badge>}
            {m.source === 'learning' && <Badge tone="ok" icon={BadgeCheck}>verified lesson{m.verified_at ? ` · ${formatTs(m.verified_at)}` : ''}</Badge>}
            {m.success_count > 0 && <Badge tone="ok">fix confirmed {m.success_count}×</Badge>}
            {m.outcome && <Badge tone={outcomeTone(m.outcome)}>{m.outcome}</Badge>}
          </div>
          <h4 className="mt-1.5 text-[15px] leading-snug font-semibold text-fg">{m.title}</h4>
          <p className="mt-0.5 text-xs text-subtle">
            <span className={`font-semibold ${TONE_TEXT[tone]}`}>{confWord(m.confidence)}</span> · {meta.join(' · ')}
          </p>
        </div>
      </div>
      <dl className="mt-4 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[90px_1fr]">
        {m.root_cause
          ? <><dt className="font-medium text-subtle">Root cause</dt><dd className="text-fg">{m.root_cause}</dd></>
          : m.summary && <><dt className="font-medium text-subtle">Problem</dt><dd className="text-fg">{m.summary}</dd></>}
        <dt className="font-medium text-subtle">Fix</dt>
        <dd className="min-w-0 text-fg">{m.resolution ? <LongText text={m.resolution} /> : <span className="text-warn">No verified fix recorded yet (open ticket)</span>}</dd>
        {m.learning && <><dt className="font-medium text-subtle">Lesson</dt><dd className="text-fg">{m.learning}</dd></>}
      </dl>
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3">
        <button onClick={() => setOpen(!open)} className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
          <ScanSearch size={14} /> Why this match <ChevronDown size={14} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
        <span className="flex-1" />
        {onWorked && (
          <Button variant="ok" size="sm" icon={CircleCheck} disabled={confirmed}
            onClick={async () => { await onWorked(m); setConfirmed(true) }}>
            {confirmed ? 'Confirmed' : 'This fix worked'}
          </Button>
        )}
        {onWriteBack && <Button variant="secondary" size="sm" onClick={() => onWriteBack(m)}>Save as lesson →</Button>}
      </div>
      <div className="reveal" data-open={open}>
        <div>
          <div className="mt-3 space-y-1.5 rounded-lg bg-surface-2 p-3 text-xs text-muted">
            {m.reasons.map((r, i) => <p key={i}>• {r}</p>)}
            {m.evidence.map((e) => (
              <p key={e.chunk_id} className="border-l-2 border-link/40 pl-2 text-subtle">
                <span className="font-semibold text-link uppercase">{e.field.replace('_', ' ')}</span> · {e.text}
              </p>
            ))}
          </div>
        </div>
      </div>
    </article>
  )
}

export function MatchList({ matches, onWorked, onWriteBack, weak }) {
  if (!matches?.length) return <Empty icon={SearchX} title="No similar past cases" />
  return (
    <div className="space-y-3">
      {weak && <p className="text-xs text-subtle">These are below 50% match, so they are <b>not</b> used as proof. Shown for reference only.</p>}
      {matches.map((m, i) => <MatchCard key={m.record_id} m={m} rank={i + 1} onWorked={onWorked} onWriteBack={onWriteBack} />)}
    </div>
  )
}

/* -------------------------------------------------------------- node history */
export function NodeHistory({ history, node }) {
  if (!history?.length) return <Empty icon={History} title="No node history">Name a node (e.g. CMG-12) to see its past changes.</Empty>
  return (
    <Card title={`Past changes on ${node}`} icon={History}>
      <ol className="space-y-3">
        {history.map((h) => (
          <li key={h.id} className="flex items-start gap-3">
            <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${outcomeTone(h.outcome) === 'bad' ? 'bg-bad' : outcomeTone(h.outcome) === 'warn' ? 'bg-warn' : 'bg-ok'}`} />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-fg">{h.title}</p>
              <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-subtle">{h.date} <Cite id={h.id} /> <Badge tone={outcomeTone(h.outcome)}>{h.outcome || '-'}</Badge></p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}

/* ------------------------------------------------------------------ skeleton */
export function ResultSkeleton() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-line bg-surface p-5 shadow-card">
        <div className="flex items-center gap-5"><Skeleton className="h-16 w-16 !rounded-full" />
          <div className="flex-1 space-y-2"><Skeleton className="h-5 w-2/3" /><Skeleton className="h-4 w-1/2" /></div></div>
      </div>
      <div className="space-y-3 rounded-xl border border-line bg-surface p-5 shadow-card">
        <Skeleton className="h-4 w-40" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-11/12" /><Skeleton className="h-4 w-4/5" />
      </div>
    </div>
  )
}

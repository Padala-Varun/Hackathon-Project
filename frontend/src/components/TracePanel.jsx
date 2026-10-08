import { useEffect, useRef, useState } from 'react'
import {
  BellRing, ChevronDown, CircleCheck, Clock, FileText, Gauge, ListOrdered, MessageCircleQuestion, PenLine, RefreshCw,
  ScanSearch, Search, ShieldCheck, SkipForward, Sparkles, TriangleAlert, Workflow,
} from 'lucide-react'
import { Empty, Spinner } from './ui'

const TOOL_TITLE = {
  search_by_symptom: 'Searched similar past cases',
  search_by_mop_step: 'Checked every MOP step',
  search_by_fingerprint: 'Matched product and release (fingerprint)',
  node_history: "Looked up the node's history",
  notify_webhook: 'Sent an alert',
}

// event type -> [icon, colour, plain-language title]
const STEP = {
  fingerprint: [ScanSearch, 'text-link', 'Understood your request'],
  clarify: [MessageCircleQuestion, 'text-accent-ink', 'Asked you a question'],
  plan: [Workflow, 'text-accent-ink', 'Made a plan'],
  tool_call: [Search, 'text-fg', null],
  tool_result: [CircleCheck, 'text-ok', 'Found'],
  tool_skip: [SkipForward, 'text-subtle', 'Skipped a repeated search'],
  requery: [RefreshCw, 'text-warn', 'Searched again with other words'],
  rank: [ListOrdered, 'text-link', 'Ranked the results'],
  risk: [Gauge, 'text-bad', 'Scored the risk'],
  draft: [FileText, 'text-muted', 'Drafted the answer'],
  llm_start: [Sparkles, 'text-link', 'AI writer is rewriting the answer'],
  llm_skipped: [PenLine, 'text-subtle', 'Used the proven template (AI writer off)'],
  llm_error: [TriangleAlert, 'text-bad', 'AI writer failed, kept the template'],
  verify: [ShieldCheck, 'text-ok', 'Checked that every line has proof'],
  notify: [BellRing, 'text-warn', 'Sent a high-risk alert to the team'],
}

function Elapsed({ running, events }) {
  const start = useRef(null)
  const [ms, setMs] = useState(0)
  useEffect(() => {
    if (!running) return
    start.current = Date.now()
    setMs(0)
    const t = setInterval(() => setMs(Date.now() - start.current), 100)
    return () => clearInterval(t)
  }, [running])
  if (!events.length) return null
  return <span className="inline-flex items-center gap-1 text-xs text-subtle"><Clock size={12} />{(ms / 1000).toFixed(1)}s</span>
}

export default function TracePanel({ events, running }) {
  const [open, setOpen] = useState(true)
  return (
    <section className="rounded-xl border border-line bg-surface shadow-card">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2.5 border-b border-line px-5 py-3 text-left">
        <Workflow size={17} className="text-subtle" />
        <span className="text-sm font-semibold text-fg">How the agent worked</span>
        {running && <Spinner className="ml-1 !h-3.5 !w-3.5" />}
        <span className="ml-auto flex items-center gap-3">
          <Elapsed running={running} events={events} />
          <span className="text-xs text-subtle">{events.length} steps</span>
          <ChevronDown size={16} className={`text-subtle transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      <div className="reveal" data-open={open}>
        <div>
          {!events.length && !running ? (
            <Empty icon={Workflow} title="Nothing yet">Run the agent to watch it understand your text, plan its searches, check the history and verify its answer.</Empty>
          ) : (
            <ol className="scroll-thin max-h-[calc(100vh-260px)] overflow-y-auto px-5 py-4">
              {events.map((ev, i) => {
                const [Icon, color, title] = STEP[ev.type] || [CircleCheck, 'text-muted', ev.type]
                const heading = ev.type === 'tool_call' ? (TOOL_TITLE[ev.data.tool] || 'Used a tool') : title
                const detail = ev.type === 'tool_call' ? ev.data.reason : ev.message
                const last = i === events.length - 1
                return (
                  <li key={i} className="animate-fade-up relative flex gap-3 pb-4 last:pb-0">
                    {!last && <span className="absolute top-7 bottom-0 left-[13px] w-px bg-line" />}
                    <span className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 ${color}`}>
                      <Icon size={14} />
                    </span>
                    <div className="min-w-0 flex-1 pt-0.5">
                      <p className="text-[13px] font-semibold text-fg">{heading}</p>
                      {detail && <p className="mt-0.5 text-xs leading-relaxed text-muted">{detail}</p>}
                      {ev.type === 'tool_call' && <p className="mt-1 truncate font-mono text-[10.5px] text-subtle" title={ev.message}>{ev.message}</p>}
                      {ev.type === 'plan' && (
                        <ol className="mt-1.5 space-y-1">
                          {ev.data.steps.map((s, j) => (
                            <li key={j} className="flex gap-2 text-xs text-muted">
                              <span className="font-semibold text-subtle">{j + 1}.</span>
                              <span>{TOOL_TITLE[s.tool] || s.tool}: <span className="text-subtle">{s.reason}</span></span>
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  </li>
                )
              })}
              {running && (
                <li className="flex items-center gap-3 pt-1 text-xs text-subtle"><Spinner className="!h-3.5 !w-3.5" /> Working…</li>
              )}
            </ol>
          )}
        </div>
      </div>
    </section>
  )
}

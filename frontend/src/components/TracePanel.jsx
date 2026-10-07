import { Card, Empty, Spinner } from './ui'

const LABEL = {
  fingerprint: ['FINGERPRINT', 'text-info'],
  clarify: ['ASK', 'text-amber'],
  plan: ['PLAN', 'text-amber'],
  tool_call: ['TOOL', 'text-ink-100'],
  tool_result: ['RESULT', 'text-ok'],
  tool_skip: ['SKIP', 'text-ink-500'],
  requery: ['RE-QUERY', 'text-warn'],
  rank: ['RANK', 'text-info'],
  risk: ['RISK', 'text-bad'],
  draft: ['DRAFT', 'text-ink-300'],
  llm_start: ['LLM', 'text-info'],
  llm_skipped: ['LLM', 'text-ink-500'],
  llm_error: ['LLM', 'text-bad'],
  verify: ['VERIFY', 'text-ok'],
  notify: ['NOTIFY', 'text-amber'],
}

export default function TracePanel({ events, running }) {
  return (
    <Card title="Agent trace" right={running ? <Spinner /> : <span className="font-mono text-[11px] text-ink-500">{events.length} steps</span>}>
      {!events.length && !running ? (
        <Empty>Run the agent to see how it fingerprints, plans, calls tools and checks citations.</Empty>
      ) : (
        <ol className="scroll-thin max-h-[70vh] space-y-2 overflow-y-auto pr-1">
          {events.map((ev, i) => {
            const [label, color] = LABEL[ev.type] || [ev.type.toUpperCase(), 'text-ink-300']
            const steps = ev.type === 'plan' ? ev.data.steps : null
            return (
              <li key={i} className="rounded-lg border border-ink-800 bg-ink-950/60 px-2.5 py-2">
                <div className="flex gap-2">
                  <span className={`w-20 shrink-0 font-mono text-[10px] font-semibold tracking-wider ${color}`}>{label}</span>
                  <span className={`text-xs leading-relaxed text-ink-300 ${ev.type === 'tool_call' ? 'font-mono text-[11px] text-ink-100' : ''}`}>
                    {ev.message}
                  </span>
                </div>
                {ev.type === 'tool_call' && ev.data.reason && <p className="ml-22 pl-0.5 text-[11px] text-ink-500">↳ {ev.data.reason}</p>}
                {steps && (
                  <ol className="ml-22 mt-1 list-decimal space-y-0.5 pl-4 text-[11px] text-ink-500">
                    {steps.map((s, j) => <li key={j}><span className="font-mono text-ink-300">{s.tool}</span> — {s.reason}</li>)}
                  </ol>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </Card>
  )
}

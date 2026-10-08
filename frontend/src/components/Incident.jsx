import { useEffect, useRef, useState } from 'react'
import { CircleAlert, Files, History, ListChecks, Search, Siren, Ticket } from 'lucide-react'
import { api } from '../api'
import PageHeader from './PageHeader'
import TracePanel from './TracePanel'
import { DetectedChips, ExampleChips } from './InputHelpers'
import { Checklist, ClarifyCard, DetailTabs, MatchList, NodeHistory, Recommendation, ResultSkeleton, VerdictBanner } from './Results'
import { useToast } from './Toast'
import { Button, Card, Field, inputCls, Kbd } from './ui'
import { useAgentRun } from './useAgentRun'

export const INCIDENT_EXAMPLES = [
  { label: 'NetAct ghost alarms', text: 'NetAct still shows alarms that the CMM already cleared and we cannot delete them' },
  { label: 'scp refused after upgrade', text: 'After upgrading the CMM to 26.7 our scp file transfer to the node is refused' },
  { label: 'Pods not created (quota)', text: 'CMM pods are not created: exceeded quota on limits.cpu and no PriorityClass found' },
  { label: 'Egress-proxy crash loop', text: 'egress-proxy pod in CrashLoopBackOff on NRD 25.7, envoy error unknown field lb_policy' },
  { label: 'Not a network problem', text: 'Office printer does not print double-sided' },
]

export default function Incident({ nodes, products = [], prefill, onWriteBack }) {
  const [text, setText] = useState('')
  const [node, setNode] = useState('')
  const [product, setProduct] = useState('')
  const [ticketId, setTicketId] = useState('')
  const [tickets, setTickets] = useState([])
  const agent = useAgentRun()
  const toast = useToast()
  const resultsRef = useRef(null)
  const r = agent.result

  useEffect(() => { api.tickets('open').then(setTickets).catch(() => {}) }, [])

  const run = (t = text, n = node, p = product) => agent.run({ mode: 'incident', text: t, node: n || null, node_type: p || null })

  useEffect(() => {
    if (!prefill) return
    setText(prefill.text)
    setNode(prefill.node || '')
    setProduct('')
    setTicketId(prefill.ticket_id || '')
    if (prefill.autorun) run(prefill.text, prefill.node || '')
  }, [prefill?.at]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (r) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [r])

  const loadTicket = (id) => {
    setTicketId(id)
    const t = tickets.find((x) => x.id === id)
    if (t) { setText(t.summary); setNode(t.node || '') }
  }

  const confirmFix = async (m) => {
    await api.feedback({ incident_text: text, verified_by: 'NOC engineer (demo)', matched_ids: [m.record_id], worked: true, ticket_id: ticketId || null })
    toast.push({ tone: 'ok', title: 'Fix confirmed', body: `${m.record_id} is marked as a proven fix and will rank higher next time.` })
  }

  return (
    <div>
      <PageHeader id="incident" icon={Siren} eyebrow="During an incident" title="Fix an incident"
        purpose="Something is broken right now. Describe what you see, and the agent finds technically similar past cases with the root cause and the fix that worked."
        hints={[
          'Paste symptoms, alarms or error lines, or load an open ticket. Error codes are matched exactly.',
          'Read the verdict: the most likely cause and how sure the agent is (% match).',
          'If the old fix works, click "This fix worked". If you found a new fix, click "Save as lesson".',
        ]} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Card>
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-[1fr_220px]">
                <Field label="Load an open ticket" hint="optional · from the ticketing system">
                  <div className="relative">
                    <Ticket size={16} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-subtle" />
                    <select className={`${inputCls} pl-9`} value={ticketId} onChange={(e) => loadTicket(e.target.value)}>
                      <option value="">Choose a ticket…</option>
                      {tickets.map((t) => <option key={t.id} value={t.id}>{t.id} ({t.type}) · {t.summary.slice(0, 70)}</option>)}
                    </select>
                  </div>
                </Field>
                {nodes.length > 0 ? (
                  <Field label="Node" hint="optional">
                    <select className={inputCls} value={node} onChange={(e) => setNode(e.target.value)}>
                      <option value="">Not sure</option>
                      {nodes.map((n) => <option key={n.node} value={n.node}>{n.node} · {n.node_type}</option>)}
                    </select>
                  </Field>
                ) : (
                  <Field label="Product" hint="optional">
                    <select className={inputCls} value={product} onChange={(e) => setProduct(e.target.value)}>
                      <option value="">Not sure</option>
                      {products.map((p) => <option key={p.node_type} value={p.node_type}>{p.node_type} ({p.records} tickets)</option>)}
                    </select>
                  </Field>
                )}
              </div>
              <Field label="What is going wrong?" hint="symptoms, alarms, log lines or commands">
                <textarea className={`${inputCls} h-28 resize-y font-mono text-[13.5px]`} value={text} onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && text.trim()) run() }}
                  placeholder="e.g. egress-proxy pod in CrashLoopBackOff on NRD 25.7 after deployment" />
              </Field>
              <DetectedChips text={text} node={node} nodeType={product} mode="incident" showNode={nodes.length > 0} />
              <ExampleChips examples={INCIDENT_EXAMPLES} onPick={(ex) => { setText(ex.text); setTicketId(''); setNode(''); setProduct('') }} />
              <div className="flex flex-wrap items-center gap-3">
                <Button size="lg" icon={Search} disabled={!text.trim() || agent.running} onClick={() => run()}>
                  {agent.running ? 'Searching…' : 'Find similar past cases'}
                </Button>
                <span className="text-xs text-subtle">or press <Kbd>Ctrl</Kbd> + <Kbd>Enter</Kbd></span>
              </div>
            </div>
          </Card>

          <div ref={resultsRef} className="scroll-mt-6 space-y-5">
            {agent.error && (
              <p className="flex items-center gap-2 rounded-xl border border-bad/30 bg-bad/8 p-4 text-sm text-bad"><CircleAlert size={16} /> {agent.error}</p>
            )}
            {agent.running && !r && !agent.llmText && <ResultSkeleton />}
            {agent.running && !r && agent.llmText && <Recommendation result={null} llmText={agent.llmText} running />}
            {r && (
              <>
                <VerdictBanner result={r} mode="incident" />
                {r.clarification && <ClarifyCard clarification={r.clarification} onAnswer={(field, v) => {
                  if (field === 'node_type') { setProduct(v); run(text, node, v) } else { setNode(v); run(text, v) }
                }} />}
                <Recommendation result={r} llmText={agent.llmText} running={agent.running} />
                <DetailTabs key={agent.runId} tabs={[
                  {
                    id: 'cases', label: r.status === 'ok' ? 'Similar past cases' : 'Closest (not used)', icon: Files, count: r.matches.length,
                    content: <MatchList matches={r.matches} weak={r.status !== 'ok'} onWorked={r.status === 'ok' ? confirmFix : null}
                      onWriteBack={(m) => onWriteBack({ incident_text: text, matched: r.status === 'ok' ? m : null, ticket_id: ticketId, node })} />,
                  },
                  { id: 'checks', label: 'What to check', icon: ListChecks, count: r.prechecks.length, show: r.prechecks.length > 0, content: <Checklist items={r.prechecks} /> },
                  { id: 'history', label: 'Node history', icon: History, count: r.node_history.length, show: r.node_history.length > 0, content: <NodeHistory history={r.node_history} node={r.fingerprint?.nodes?.[0]} /> },
                ]} />
              </>
            )}
          </div>
        </div>
        <aside className="xl:sticky xl:top-6 xl:self-start">
          <TracePanel events={agent.events} running={agent.running} />
        </aside>
      </div>
    </div>
  )
}

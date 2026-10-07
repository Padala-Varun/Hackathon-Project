import { useEffect, useState } from 'react'
import { api } from '../api'
import TracePanel from './TracePanel'
import { Checklist, ClarifyCard, MatchCard, NodeHistory, RecommendationPanel } from './Results'
import { Button, Card, Field, inputCls } from './ui'
import { useAgentRun } from './useAgentRun'

export default function Incident({ nodes, onWriteBack }) {
  const [text, setText] = useState('')
  const [node, setNode] = useState('')
  const [ticketId, setTicketId] = useState('')
  const [tickets, setTickets] = useState([])
  const agent = useAgentRun()
  const r = agent.result

  useEffect(() => { api.tickets('open').then(setTickets).catch(() => {}) }, [])

  const run = (n = node) => agent.run({ mode: 'incident', text, node: n || null })

  const loadTicket = (id) => {
    setTicketId(id)
    const t = tickets.find((x) => x.id === id)
    if (t) { setText(t.summary); setNode(t.node || '') }
  }

  const confirmFix = (m) =>
    api.feedback({ incident_text: text, verified_by: 'NOC engineer (demo)', matched_ids: [m.record_id], worked: true, ticket_id: ticketId || null })

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-5">
        <Card title="Live incident">
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-[1fr_200px]">
              <Field label="Load from ticketing system" hint="mock ticket API">
                <select className={inputCls} value={ticketId} onChange={(e) => loadTicket(e.target.value)}>
                  <option value="">— choose an open ticket —</option>
                  {tickets.map((t) => <option key={t.id} value={t.id}>{t.id} · {t.summary.slice(0, 80)}</option>)}
                </select>
              </Field>
              <Field label="Node" hint="optional">
                <select className={inputCls} value={node} onChange={(e) => setNode(e.target.value)}>
                  <option value="">unknown</option>
                  {nodes.map((n) => <option key={n.node} value={n.node}>{n.node} · {n.node_type}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Symptoms, alarms, log lines or commands" hint="paste anything - error codes are fingerprinted">
              <textarea className={`${inputCls} h-28 resize-y font-mono text-[13px]`} value={text} onChange={(e) => setText(e.target.value)}
                placeholder="e.g. %BGP-5-ADJCHANGE neighbor Down - hold time expired, started right after the SMU install on ER-22" />
            </Field>
            <Button disabled={!text.trim() || agent.running} onClick={() => run()}>Find similar past cases</Button>
          </div>
        </Card>

        {agent.error && <p className="rounded-lg border border-bad/40 bg-bad/10 p-3 text-sm text-bad">{agent.error}</p>}
        {r?.clarification && <ClarifyCard clarification={r.clarification} onAnswer={(_, v) => { setNode(v); run(v) }} />}
        {(agent.running || r) && <RecommendationPanel result={r} llmText={agent.llmText} running={agent.running} mode="incident" />}

        {r && (
          <>
            <Card title={r.status === 'ok' ? `Technically similar past cases · ${r.matches.length}` : 'Closest candidates (below threshold - not used as evidence)'}>
              <div className="space-y-3">
                {r.matches.map((m, i) => (
                  <MatchCard key={m.record_id} m={m} rank={i + 1}
                    onWorked={r.status === 'ok' ? confirmFix : null}
                    onWriteBack={() => onWriteBack({ incident_text: text, matched: r.status === 'ok' ? m : null, ticket_id: ticketId, node })} />
                ))}
              </div>
            </Card>
            <Checklist title="What to validate" items={r.prechecks} />
            <NodeHistory history={r.node_history} node={r.fingerprint?.nodes?.[0]} />
          </>
        )}
      </div>
      <div className="lg:sticky lg:top-4 lg:self-start">
        <TracePanel events={agent.events} running={agent.running} />
      </div>
    </div>
  )
}

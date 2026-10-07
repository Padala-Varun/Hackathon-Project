import { useEffect, useState } from 'react'
import TracePanel from './TracePanel'
import { Checklist, ClarifyCard, MatchCard, MopSteps, NodeHistory, RecommendationPanel, RiskPanel } from './Results'
import { Button, Card, Field, inputCls } from './ui'
import { useAgentRun } from './useAgentRun'

const SAMPLE = 'Software upgrade on packet core gateway CMG-12 using MOP-UPG-04'

export default function PreChange({ nodes, mops }) {
  const [text, setText] = useState('')
  const [form, setForm] = useState({ node: '', mop_id: '', release: '' })
  const agent = useAgentRun()
  const r = agent.result

  const submit = (overrides = {}, extra = {}, t = text) => {
    const f = { ...form, ...overrides }
    setForm(f)
    agent.run({ mode: 'pre_change', text: t, node: f.node || null, mop_id: f.mop_id || null, release: f.release || null, ...extra })
  }

  // One-click demo: open the app with #demo to run the brief's sample scenario.
  useEffect(() => {
    if (window.location.hash === '#demo') {
      setText(SAMPLE)
      submit({ release: '24.3' }, {}, SAMPLE)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-5">
        <Card title="Planned LNI">
          <div className="space-y-3">
            <Field label="What are you about to change?" hint="free text - node, MOP and release are detected automatically">
              <textarea className={`${inputCls} h-20 resize-y`} value={text} onChange={(e) => setText(e.target.value)}
                placeholder="e.g. Firmware upgrade on edge router ER-21 to 7.11.1 using MOP-RTR-07" />
            </Field>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Node" hint="optional">
                <select className={inputCls} value={form.node} onChange={(e) => setForm({ ...form, node: e.target.value })}>
                  <option value="">auto-detect</option>
                  {nodes.map((n) => <option key={n.node} value={n.node}>{n.node} · {n.node_type}</option>)}
                </select>
              </Field>
              <Field label="MOP" hint="optional">
                <select className={inputCls} value={form.mop_id} onChange={(e) => setForm({ ...form, mop_id: e.target.value })}>
                  <option value="">auto-detect</option>
                  {mops.map((m) => <option key={m.mop_id} value={m.mop_id}>{m.mop_id} · {m.title}</option>)}
                </select>
              </Field>
              <Field label="Target release" hint="optional">
                <input className={inputCls} value={form.release} onChange={(e) => setForm({ ...form, release: e.target.value })} placeholder="e.g. 24.3" />
              </Field>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button disabled={!text.trim() || agent.running} onClick={() => submit()}>Check for known pitfalls</Button>
              <Button variant="ghost" onClick={() => { setText(SAMPLE); setForm({ node: '', mop_id: '', release: '' }) }}>Load sample scenario</Button>
            </div>
          </div>
        </Card>

        {agent.error && <p className="rounded-lg border border-bad/40 bg-bad/10 p-3 text-sm text-bad">{agent.error}</p>}
        {r?.status === 'needs_clarification' && (
          <ClarifyCard blocking clarification={r.clarification}
            onAnswer={(field, value) => (field ? submit({ [field]: value }) : submit({}, { skip_clarification: true }))} />
        )}

        {(agent.running || (r && r.status !== 'needs_clarification')) && (
          <RecommendationPanel result={r?.status !== 'needs_clarification' ? r : null} llmText={agent.llmText} running={agent.running} mode="pre_change" />
        )}

        {r && r.status !== 'needs_clarification' && (
          <>
            <div className="grid gap-5 xl:grid-cols-2">
              {r.risk && <RiskPanel risk={r.risk} notification={r.notification} />}
              <Checklist title={r.status === 'ok' ? 'Validation steps from past LNIs' : 'General pre-checks'} items={r.prechecks} />
            </div>
            <MopSteps mopId={r.mop_id} steps={r.mop_steps} />
            {r.status === 'ok' && (
              <Card title={`Similar past LNIs · ${r.matches.length}`}>
                <div className="space-y-3">{r.matches.map((m, i) => <MatchCard key={m.record_id} m={m} rank={i + 1} />)}</div>
              </Card>
            )}
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

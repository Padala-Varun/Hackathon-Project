import { useEffect, useRef, useState } from 'react'
import { ChevronDown, CircleAlert, Files, FileText, History, ListChecks, ShieldAlert, ShieldCheck } from 'lucide-react'
import PageHeader from './PageHeader'
import TracePanel from './TracePanel'
import { DetectedChips, ExampleChips } from './InputHelpers'
import { Checklist, ClarifyCard, DetailTabs, MatchList, MopSteps, NodeHistory, Recommendation, ResultSkeleton, VerdictBanner } from './Results'
import { useToast } from './Toast'
import { Button, Card, Field, inputCls, Kbd } from './ui'
import { useAgentRun } from './useAgentRun'

export const PLAN_EXAMPLES = [
  { label: 'CMM upgrade to 26.7', text: 'Upgrade the CMM to software release 26.7' },
  { label: 'CMG deploy with operator pod', text: 'Fresh CMG 26.7 deployment on a cloud platform using the operator pod' },
  { label: 'CMM deployment on Kubernetes', text: 'Deploy CMM 25.7 on NCS Kubernetes with IPDS pods' },
  { label: 'Standalone NSSF on NCP', text: 'Deploy a standalone NSSF 25.7 over NCP and give OAM access over SSH' },
]
const EMPTY_FORM = { node: '', node_type: '', mop_id: '', release: '' }

export default function PreChange({ nodes, mops, products = [], prefill }) {
  const [text, setText] = useState('')
  const [form, setForm] = useState(EMPTY_FORM)
  const [advanced, setAdvanced] = useState(false)
  const agent = useAgentRun()
  const toast = useToast()
  const resultsRef = useRef(null)
  const r = agent.result

  const runWith = (t, f, extra = {}) =>
    agent.run({ mode: 'pre_change', text: t, node: f.node || null, node_type: f.node_type || null, mop_id: f.mop_id || null, release: f.release || null, ...extra })
  const submit = (overrides = {}, extra = {}) => {
    const f = { ...form, ...overrides }
    setForm(f)
    runWith(text, f, extra)
  }

  // Prefill from the Home page, the #demo link, etc.
  useEffect(() => {
    if (!prefill) return
    const f = { ...EMPTY_FORM, ...(prefill.form || {}) }
    setText(prefill.text)
    setForm(f)
    if (prefill.autorun) runWith(prefill.text, f)
  }, [prefill?.at]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!r) return
    resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    if (r.notification) toast.push({ tone: 'warn', title: 'High-risk alert sent', body: 'A Teams-style card was sent to the team channel (mock webhook).' })
  }, [r]) // eslint-disable-line react-hooks/exhaustive-deps

  const flagged = r?.mop_steps?.filter((s) => s.warnings.length).length || 0

  return (
    <div>
      <PageHeader id="plan" icon={ShieldAlert} eyebrow="Before the change" title="Plan a change"
        purpose="Describe the change you are about to make. The agent checks similar past changes for known pitfalls, then gives you a check-list and a risk score."
        hints={[
          'Describe your change in normal words: which product, which release, what you will do. Or click an example.',
          'If a detail is missing, the agent asks you one quick question. Click an answer.',
          'Read the verdict, tick the check-list, and click any blue ID to see the past record behind it.',
        ]} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 space-y-5">
          <Card>
            <div className="space-y-4">
              <Field label="What are you about to change?">
                <textarea className={`${inputCls} h-24 resize-y text-[15px]`} value={text} onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && text.trim()) submit() }}
                  placeholder="e.g. Upgrade the CMM to software release 26.7" />
              </Field>
              <DetectedChips text={text} node={form.node} mop={form.mop_id} release={form.release} nodeType={form.node_type} mode="pre_change"
                showMop={mops.length > 0} showNode={nodes.length > 0} />
              <ExampleChips examples={PLAN_EXAMPLES} onPick={(ex) => { setText(ex.text); setForm(EMPTY_FORM) }} />

              <div className="rounded-lg border border-line">
                <button onClick={() => setAdvanced(!advanced)} className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-[13px] font-medium text-muted hover:text-fg">
                  Advanced: choose {nodes.length > 0 ? 'node, ' : 'product, '}{mops.length > 0 ? 'MOP or ' : ''}release yourself <span className="text-xs text-subtle">(optional)</span>
                  <ChevronDown size={15} className={`ml-auto transition-transform ${advanced ? 'rotate-180' : ''}`} />
                </button>
                <div className="reveal" data-open={advanced}>
                  <div>
                    <div className="grid gap-3 border-t border-line p-3.5 sm:grid-cols-3">
                      {nodes.length > 0 ? (
                        <Field label="Node">
                          <select className={inputCls} value={form.node} onChange={(e) => setForm({ ...form, node: e.target.value })}>
                            <option value="">Detect from text</option>
                            {nodes.map((n) => <option key={n.node} value={n.node}>{n.node} · {n.node_type}</option>)}
                          </select>
                        </Field>
                      ) : (
                        <Field label="Product">
                          <select className={inputCls} value={form.node_type} onChange={(e) => setForm({ ...form, node_type: e.target.value })}>
                            <option value="">Detect from text</option>
                            {products.map((p) => <option key={p.node_type} value={p.node_type}>{p.node_type} ({p.records} tickets)</option>)}
                          </select>
                        </Field>
                      )}
                      {mops.length > 0 && (
                        <Field label="MOP">
                          <select className={inputCls} value={form.mop_id} onChange={(e) => setForm({ ...form, mop_id: e.target.value })}>
                            <option value="">Detect from text</option>
                            {mops.map((m) => <option key={m.mop_id} value={m.mop_id}>{m.mop_id} · {m.title}</option>)}
                          </select>
                        </Field>
                      )}
                      <Field label="Target release">
                        <input className={inputCls} value={form.release} onChange={(e) => setForm({ ...form, release: e.target.value })} placeholder="e.g. 24.3" />
                      </Field>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Button size="lg" icon={ShieldCheck} disabled={!text.trim() || agent.running} onClick={() => submit()}>
                  {agent.running ? 'Checking…' : 'Check for known pitfalls'}
                </Button>
                <span className="text-xs text-subtle">or press <Kbd>Ctrl</Kbd> + <Kbd>Enter</Kbd></span>
              </div>
            </div>
          </Card>

          <div ref={resultsRef} className="scroll-mt-6 space-y-5">
            {agent.error && (
              <p className="flex items-center gap-2 rounded-xl border border-bad/30 bg-bad/8 p-4 text-sm text-bad"><CircleAlert size={16} /> {agent.error}</p>
            )}
            {r?.status === 'needs_clarification' && (
              <ClarifyCard blocking clarification={r.clarification}
                onAnswer={(field, value) => (field ? submit({ [field]: value }) : submit({}, { skip_clarification: true }))} />
            )}
            {agent.running && !r && !agent.llmText && <ResultSkeleton />}
            {agent.running && !r && agent.llmText && <Recommendation result={null} llmText={agent.llmText} running />}
            {r && r.status !== 'needs_clarification' && (
              <>
                <VerdictBanner result={r} mode="pre_change" />
                <Recommendation result={r} llmText={agent.llmText} running={agent.running} />
                <DetailTabs key={agent.runId} tabs={[
                  { id: 'checks', label: 'Check-list', icon: ListChecks, count: r.prechecks.length, content: <Checklist items={r.prechecks} /> },
                  { id: 'mop', label: 'MOP steps', icon: FileText, count: flagged ? `${flagged} risky` : null, show: r.mop_steps.length > 0, content: <MopSteps mopId={r.mop_id} steps={r.mop_steps} /> },
                  { id: 'cases', label: r.status === 'ok' ? 'Similar past changes' : 'Closest (not used)', icon: Files, count: r.matches.length, content: <MatchList matches={r.matches} weak={r.status !== 'ok'} /> },
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

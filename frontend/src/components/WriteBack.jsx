import { useContext, useEffect, useState } from 'react'
import { BadgeCheck, BookmarkCheck, CircleAlert, Eye, Search } from 'lucide-react'
import { api } from '../api'
import PageHeader from './PageHeader'
import { useToast } from './Toast'
import { Badge, Button, Card, Cite, Field, formatTs, inputCls, RecordContext } from './ui'

const EMPTY = { incident_text: '', title: '', verified_root_cause: '', verified_fix: '', learning: '', verified_by: '', node: '', ticket_id: '', matched_ids: [], components: '', build: '', rca_category: '' }

function Step({ n, title, children }) {
  return (
    <div className="relative pl-10">
      <span className="absolute top-0 left-0 flex h-7 w-7 items-center justify-center rounded-full bg-accent/15 text-xs font-bold text-accent-ink">{n}</span>
      <p className="mb-3 pt-1 text-sm font-semibold text-fg">{title}</p>
      <div className="space-y-3">{children}</div>
    </div>
  )
}

export default function WriteBack({ draft, onSaved, onFindNow }) {
  const [f, setF] = useState(EMPTY)
  const [saved, setSaved] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const { open } = useContext(RecordContext)
  const [options, setOptions] = useState({ components: [], builds: [], rca_categories: [] })

  useEffect(() => { api.lessonOptions().then(setOptions).catch(() => {}) }, [])

  useEffect(() => {
    if (!draft) return
    const m = draft.matched
    setF({
      ...EMPTY,
      incident_text: draft.incident_text || '', node: draft.node || '', ticket_id: draft.ticket_id || '',
      matched_ids: m ? [m.record_id, ...m.duplicates.map((d) => d.record_id)] : [],
      verified_root_cause: m?.root_cause || '', verified_fix: m?.resolution || '', learning: m?.learning || '',
      components: m?.node_type || '',
    })
    setSaved(null)
    // take Components / Build / RCA category from the ticket we start from (the engineer can change them)
    if (m) {
      api.case(m.record_id).then((r) => setF((cur) => ({
        ...cur,
        components: r.extra?.Components || cur.components,
        build: r.extra?.Build || r.release || cur.build,
        rca_category: r.extra?.['RCA category'] || cur.rca_category,
      }))).catch(() => {})
    }
  }, [draft])

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const required = [['components', 'Components'], ['build', 'Build'], ['rca_category', 'RCA category']]
  const missingFields = required.filter(([k]) => !f[k].trim()).map(([, label]) => label)
  const missing = !f.incident_text.trim() ? 'Describe what went wrong (step 1).'
    : missingFields.length ? `Fill in ${missingFields.join(', ')} (step 1, required).`
      : !(f.verified_root_cause.trim() || f.verified_fix.trim()) ? 'Add the root cause or the fix (step 2).'
        : !f.verified_by.trim() ? 'Your name is required: a human confirms every lesson (step 3).' : ''

  const submit = async () => {
    setBusy(true); setError('')
    try {
      const res = await api.feedback({ ...f, ticket_id: f.ticket_id || null })
      setSaved(res)
      onSaved?.(res)
      toast.push({
        tone: 'ok', title: 'Lesson saved',
        body: `${res.record?.id || 'Record'} saved on ${formatTs(res.record?.verified_at) || 'now'} and is now part of the team's memory.`,
        action: res.record ? { label: 'View record', onClick: () => open(res.record.id) } : null,
      })
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div>
      <PageHeader id="save" icon={BookmarkCheck} eyebrow="After it is fixed" title="Save a lesson"
        purpose="Write down what really fixed the problem. It becomes a verified record that the agent finds and cites next time, so the team never solves it twice."
        hints={[
          'Easiest: on "Fix an incident", click "Save as lesson" on a result card. This form fills itself.',
          'Correct the root cause and the fix so they say what really happened.',
          'Enter your name and save. Then search again: your lesson shows up first.',
        ]} />

      {saved ? (
        <div className="animate-fade-up mx-auto max-w-2xl rounded-xl border border-ok/30 bg-ok/8 p-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-ok/15 text-ok"><BadgeCheck size={26} /></div>
          <p className="text-lg font-semibold text-fg">Lesson saved</p>
          {saved.record && (
            <p className="mt-1 text-sm text-muted">
              <b className="text-fg">{saved.record.id}</b> saved on <b className="text-fg">{formatTs(saved.record.verified_at)}</b> by <b className="text-fg">{saved.record.verified_by}</b>.
            </p>
          )}
          <p className="mt-1 text-sm text-muted">{saved.message}.</p>
          {saved.ticket && <p className="mt-1 text-sm text-muted">Ticket {saved.ticket.id} is now <b className="text-ok">{saved.ticket.status}</b>.</p>}
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {saved.record && <Button variant="secondary" icon={Eye} onClick={() => open(saved.record.id)}>View record {saved.record.id}</Button>}
            <Button icon={Search} onClick={() => onFindNow?.(f.incident_text)}>Find it now</Button>
            <Button variant="ghost" onClick={() => { setSaved(null); setF(EMPTY) }}>Save another</Button>
          </div>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          <Card>
            <div className="space-y-7">
              <Step n={1} title="What happened?">
                <Field label="Incident / symptoms">
                  <textarea className={`${inputCls} h-20`} value={f.incident_text} onChange={set('incident_text')} placeholder="What was going wrong?" />
                </Field>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label="Short title" hint="optional"><input className={inputCls} value={f.title} onChange={set('title')} /></Field>
                  <Field label="Node" hint="optional"><input className={inputCls} value={f.node} onChange={set('node')} placeholder="CMG-12" /></Field>
                  <Field label="Ticket" hint="optional"><input className={inputCls} value={f.ticket_id} onChange={set('ticket_id')} placeholder="INC-5002" /></Field>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label="Components" hint="required">
                    <input className={inputCls} list="opt-components" value={f.components} onChange={set('components')} placeholder="e.g. CMM" />
                  </Field>
                  <Field label="Build" hint="required">
                    <input className={inputCls} list="opt-builds" value={f.build} onChange={set('build')} placeholder="e.g. 26.7.0.1" />
                  </Field>
                  <Field label="RCA category" hint="required">
                    <input className={inputCls} list="opt-rca" value={f.rca_category} onChange={set('rca_category')} placeholder="e.g. Nokia-Config" />
                  </Field>
                </div>
                <datalist id="opt-components">{options.components.map((v) => <option key={v} value={v} />)}</datalist>
                <datalist id="opt-builds">{options.builds.map((v) => <option key={v} value={v} />)}</datalist>
                <datalist id="opt-rca">{options.rca_categories.map((v) => <option key={v} value={v} />)}</datalist>
                {f.matched_ids.length > 0 && <p className="text-xs text-subtle">Builds on past record(s): {f.matched_ids.map((id) => <Cite key={id} id={id} />)}</p>}
              </Step>
              <Step n={2} title="What really fixed it?">
                <Field label="Verified root cause"><textarea className={`${inputCls} h-20`} value={f.verified_root_cause} onChange={set('verified_root_cause')} /></Field>
                <Field label="Verified fix"><textarea className={`${inputCls} h-20`} value={f.verified_fix} onChange={set('verified_fix')} /></Field>
                <Field label="Lesson for next time" hint="a check to do before or after"><textarea className={`${inputCls} h-16`} value={f.learning} onChange={set('learning')} /></Field>
              </Step>
              <Step n={3} title="Who confirms it?">
                <Field label="Verified by" hint="required">
                  <input className={inputCls} value={f.verified_by} onChange={set('verified_by')} placeholder="Your name" />
                </Field>
              </Step>
              <div className="flex flex-wrap items-center gap-3 border-t border-line pt-5">
                <Button size="lg" icon={BookmarkCheck} disabled={busy || !!missing} onClick={submit}>{busy ? 'Saving…' : 'Save verified lesson'}</Button>
                {missing && <span className="text-xs text-subtle">{missing}</span>}
              </div>
              {error && <p className="flex items-center gap-2 text-sm text-bad"><CircleAlert size={15} />{error}</p>}
            </div>
          </Card>

          <aside className="lg:sticky lg:top-6 lg:self-start">
            <Card title="Preview of the saved record" icon={Eye}>
              <div className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-1.5">
                  <Badge tone="ok" icon={BadgeCheck}>Verified lesson</Badge>
                  {f.node && <Badge>{f.node.toUpperCase()}</Badge>}
                  {f.components && <Badge>{f.components}</Badge>}
                  {f.build && <Badge>Build {f.build}</Badge>}
                  {f.rca_category && <Badge>RCA: {f.rca_category}</Badge>}
                  {f.verified_by && <Badge>by {f.verified_by}</Badge>}
                </div>
                <p className="font-semibold text-fg">{f.title || (f.incident_text.length > 90 ? `${f.incident_text.slice(0, 90).replace(/\s+\S*$/, '')}…` : f.incident_text) || 'Untitled lesson'}</p>
                {[['Symptoms', f.incident_text], ['Root cause', f.verified_root_cause], ['Fix', f.verified_fix], ['Lesson', f.learning]].map(([k, v]) => (
                  <div key={k}>
                    <p className="text-xs font-semibold tracking-wide text-subtle uppercase">{k}</p>
                    <p className={v ? 'text-fg' : 'text-subtle italic'}>{v || 'not filled in yet'}</p>
                  </div>
                ))}
                <p className="border-t border-line pt-3 text-xs text-subtle">The date and time are added automatically when you save. After saving, this record is searchable immediately and cited as proof in future answers.</p>
              </div>
            </Card>
          </aside>
        </div>
      )}
    </div>
  )
}

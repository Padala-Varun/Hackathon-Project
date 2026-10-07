import { useEffect, useState } from 'react'
import { api } from '../api'
import { Button, Card, Cite, Field, inputCls, Pill } from './ui'

const EMPTY = { incident_text: '', title: '', verified_root_cause: '', verified_fix: '', learning: '', verified_by: '', node: '', ticket_id: '', matched_ids: [] }

export default function WriteBack({ draft }) {
  const [f, setF] = useState(EMPTY)
  const [saved, setSaved] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!draft) return
    const m = draft.matched
    setF({
      ...EMPTY,
      incident_text: draft.incident_text || '',
      node: draft.node || '',
      ticket_id: draft.ticket_id || '',
      matched_ids: m ? [m.record_id, ...m.duplicates.map((d) => d.record_id)] : [],
      verified_root_cause: m?.root_cause || '',
      verified_fix: m?.resolution || '',
      learning: m?.learning || '',
    })
    setSaved(null)
  }, [draft])

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = async () => {
    setBusy(true); setError('')
    try {
      setSaved(await api.feedback({ ...f, ticket_id: f.ticket_id || null }))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Card title="Write back a verified learning · after resolution" accent>
        <p className="mb-4 text-sm text-ink-300">
          The engineer confirms what actually fixed the incident. It is stored as a <b>verified</b> record, indexed immediately and
          cited in future recommendations. The ticket is updated through the ticketing API.
        </p>
        <div className="space-y-3">
          <Field label="Incident / symptoms"><textarea className={`${inputCls} h-20`} value={f.incident_text} onChange={set('incident_text')} /></Field>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Short title" hint="optional"><input className={inputCls} value={f.title} onChange={set('title')} /></Field>
            <Field label="Node" hint="optional"><input className={inputCls} value={f.node} onChange={set('node')} /></Field>
            <Field label="Ticket" hint="optional"><input className={inputCls} value={f.ticket_id} onChange={set('ticket_id')} placeholder="INC-5002" /></Field>
          </div>
          {f.matched_ids.length > 0 && (
            <p className="text-xs text-ink-300">Builds on past record(s): {f.matched_ids.map((id) => <Cite key={id} id={id} />)}</p>
          )}
          <Field label="Verified root cause"><textarea className={`${inputCls} h-16`} value={f.verified_root_cause} onChange={set('verified_root_cause')} /></Field>
          <Field label="Verified fix"><textarea className={`${inputCls} h-16`} value={f.verified_fix} onChange={set('verified_fix')} /></Field>
          <Field label="Learning / pre-check for next time"><textarea className={`${inputCls} h-14`} value={f.learning} onChange={set('learning')} /></Field>
          <Field label="Verified by" hint="required - a human validates every learning">
            <input className={inputCls} value={f.verified_by} onChange={set('verified_by')} placeholder="your name" />
          </Field>
          <Button disabled={busy || !f.verified_by.trim() || !f.incident_text.trim() || !(f.verified_root_cause.trim() || f.verified_fix.trim())} onClick={submit}>
            Save verified learning
          </Button>
          {error && <p className="text-sm text-bad">{error}</p>}
        </div>
      </Card>
      {saved && (
        <Card title="Saved">
          <p className="mb-2 text-sm text-ok">✓ {saved.message}</p>
          {saved.record && <p className="text-sm text-ink-300">New record <Cite id={saved.record.id} /> <Pill tone="ok">verified by {saved.record.verified_by}</Pill> — try the Incident tab again: it now ranks first.</p>}
          {saved.ticket && <p className="mt-1 text-sm text-ink-300">Ticket {saved.ticket.id} → <Pill tone="ok">{saved.ticket.status}</Pill></p>}
        </Card>
      )}
    </div>
  )
}

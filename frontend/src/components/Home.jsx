import { useEffect, useState } from 'react'
import {
  ArrowRight, BadgeCheck, BookmarkCheck, BookOpen, Database, FileText, Play, Repeat, SearchX, ShieldAlert, ShieldCheck, Siren,
} from 'lucide-react'
import { api } from '../api'
import { PLAN_EXAMPLES } from './PreChange'
import { INCIDENT_EXAMPLES } from './Incident'
import { Button } from './ui'

const MOMENTS = [
  {
    id: 'plan', step: 'Before the change', title: 'Plan a change', icon: ShieldAlert, tint: 'text-accent-ink bg-accent/12',
    type: 'The change you are about to make, e.g. "Upgrade the CMM to release 26.7".',
    get: 'Known pitfalls from similar past tickets, a check-list of lessons and a risk score.',
  },
  {
    id: 'incident', step: 'During an incident', title: 'Fix an incident', icon: Siren, tint: 'text-bad bg-bad/10',
    type: 'What is going wrong: symptoms, alarms or error lines.',
    get: 'The most similar past cases, their root cause, the fix that worked, and what to check, with a % match.',
  },
  {
    id: 'save', step: 'After it is fixed', title: 'Save a lesson', icon: BookmarkCheck, tint: 'text-ok bg-ok/10',
    type: 'The real root cause and fix, plus your name.',
    get: 'A verified record. The next search finds it at once, so the team never solves the same problem twice.',
  },
]

const WORDS = [
  ['LNI', 'Live Network Intervention: a planned change on live network equipment.'],
  ['MOP', 'Method of Procedure: the step-by-step instructions for a change.'],
  ['Root cause', 'The real reason a problem happened.'],
  ['Product', 'What a ticket is about: CMM (mobility manager), CMG (packet gateway), NRD (NRF / NSSF).'],
  ['% match', 'How sure the agent is. Below 50% is never used as proof.'],
]

export default function Home({ health, products = [], onNavigate }) {
  const [recurring, setRecurring] = useState(null)
  useEffect(() => { api.trends().then((t) => setRecurring(t.recurring.length)).catch(() => {}) }, [])

  const tryExample = (id) => {
    if (id === 'plan') onNavigate('plan', { text: PLAN_EXAMPLES[0].text, autorun: true })
    else if (id === 'incident') onNavigate('incident', { text: INCIDENT_EXAMPLES[0].text, autorun: true })
    else onNavigate('save')
  }

  return (
    <div className="space-y-8">
      {/* hero */}
      <section className="relative overflow-hidden rounded-2xl border border-line bg-surface p-8 shadow-card sm:p-10">
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-accent/15 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-28 left-1/3 h-64 w-64 rounded-full bg-link/10 blur-3xl" />
        <div className="relative max-w-3xl">
          <p className="text-xs font-semibold tracking-wide text-accent-ink uppercase">AI Incident Learning &amp; Prevention Agent</p>
          <h1 className="mt-2 text-3xl leading-tight font-bold tracking-tight text-fg sm:text-4xl">Institutional memory for every network change</h1>
          <p className="mt-3 text-base leading-relaxed text-muted">
            Engineers keep hitting problems the company already solved, because old tickets are written in different words and hard to find.
            This agent has learned from the team's real knowledge-base tickets,
            <b className="text-fg">warns you before a change</b>, <b className="text-fg">finds the old fix during an incident</b>,
            and <b className="text-fg">remembers the new fix afterwards</b>.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button size="lg" icon={Play} onClick={() => tryExample('plan')}>Run the 60-second demo</Button>
            <Button size="lg" variant="secondary" icon={Siren} onClick={() => onNavigate('incident')}>I have an incident</Button>
          </div>
        </div>
      </section>

      {/* the three moments */}
      <section>
        <div className="mb-3 flex items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold text-fg">Three moments, one memory</h2>
            <p className="text-sm text-muted">Pick the moment you are in. Each saved lesson makes the next warning and the next search better.</p>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {MOMENTS.map((m, i) => (
            <div key={m.id} className="lift group relative flex flex-col rounded-xl border border-line bg-surface p-5 shadow-card">
              <div className="flex items-center gap-3">
                <div className={`rounded-lg p-2.5 ${m.tint}`}><m.icon size={20} /></div>
                <div>
                  <p className="text-xs font-semibold text-subtle">{i + 1} · {m.step}</p>
                  <p className="text-base font-semibold text-fg">{m.title}</p>
                </div>
              </div>
              <dl className="mt-4 flex-1 space-y-2.5 text-sm">
                <div><dt className="text-xs font-semibold tracking-wide text-subtle uppercase">You type</dt><dd className="text-muted">{m.type}</dd></div>
                <div><dt className="text-xs font-semibold tracking-wide text-subtle uppercase">You get</dt><dd className="text-muted">{m.get}</dd></div>
              </dl>
              <div className="mt-5 flex gap-2">
                {m.id !== 'save' && <Button size="sm" icon={Play} onClick={() => tryExample(m.id)}>Try an example</Button>}
                <Button size="sm" variant="secondary" onClick={() => onNavigate(m.id)}>Open <ArrowRight size={14} /></Button>
              </div>
              {i < 2 && <ArrowRight size={18} className="absolute top-1/2 -right-3.5 z-10 hidden rounded-full border border-line bg-surface p-0.5 text-subtle lg:block" />}
            </div>
          ))}
        </div>
      </section>

      {/* stats + principles */}
      <section className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <div className="grid grid-cols-2 gap-4">
          {[
            [Database, health?.records ?? '-', 'past tickets learned'],
            health?.mops ? [FileText, health.mops, 'step-by-step MOPs'] : [FileText, products.length || '-', 'products covered'],
            [BadgeCheck, health?.learnings ?? '-', 'verified lessons saved'],
            [Repeat, recurring ?? '-', 'problems that repeat'],
          ].map(([Icon, v, label]) => (
            <div key={label} className="flex items-center gap-3 rounded-xl border border-line bg-surface p-4 shadow-card">
              <div className="rounded-lg bg-surface-3 p-2 text-muted"><Icon size={18} /></div>
              <div><p className="text-xl leading-tight font-bold text-fg">{v}</p><p className="text-xs text-subtle">{label}</p></div>
            </div>
          ))}
        </div>
        <div className="rounded-xl border border-line bg-surface p-5 shadow-card">
          <p className="mb-3 text-sm font-semibold text-fg">Rules the agent always follows</p>
          <ul className="space-y-2.5 text-sm text-muted">
            <li className="flex gap-2.5"><ShieldCheck size={17} className="mt-0.5 shrink-0 text-ok" /><span><b className="text-fg">It never changes the network.</b> It only advises; the engineer decides.</span></li>
            <li className="flex gap-2.5"><BadgeCheck size={17} className="mt-0.5 shrink-0 text-link" /><span><b className="text-fg">Every line has proof:</b> a blue ID you can click to read the original record.</span></li>
            <li className="flex gap-2.5"><SearchX size={17} className="mt-0.5 shrink-0 text-warn" /><span><b className="text-fg">No guessing.</b> If nothing similar exists, it says "No verified match found".</span></li>
          </ul>
        </div>
      </section>

      {/* glossary */}
      <section className="rounded-xl border border-line bg-surface-2 p-5">
        <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-fg"><BookOpen size={16} className="text-subtle" /> Words to know</p>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-5">
          {WORDS.map(([w, d]) => (
            <div key={w}><dt className="text-sm font-semibold text-fg">{w}</dt><dd className="text-xs leading-relaxed text-muted">{d}</dd></div>
          ))}
        </dl>
      </section>
    </div>
  )
}

import { createContext, useContext } from 'react'

export const RecordContext = createContext({ open: () => {} })

export function Card({ title, right, children, className = '', accent }) {
  return (
    <section className={`rounded-xl border bg-ink-900 ${accent ? 'border-amber/60' : 'border-ink-700'} ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-ink-800 px-4 py-2.5">
          <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-amber">{title}</h3>
          {right}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Button({ children, variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-amber text-ink-950 hover:brightness-110',
    ghost: 'border border-ink-700 text-ink-100 hover:border-ink-500 hover:bg-ink-850',
    ok: 'border border-ok/50 text-ok hover:bg-ok/10',
  }
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${styles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

const TONES = {
  amber: 'border-amber/40 bg-amber/10 text-amber',
  ok: 'border-ok/40 bg-ok/10 text-ok',
  warn: 'border-warn/40 bg-warn/10 text-warn',
  bad: 'border-bad/40 bg-bad/10 text-bad',
  info: 'border-info/40 bg-info/10 text-info',
  dim: 'border-ink-700 bg-ink-850 text-ink-300',
}

export function Pill({ tone = 'dim', children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${TONES[tone]} ${className}`}>
      {children}
    </span>
  )
}

export const confTone = (v) => (v >= 80 ? 'ok' : v >= 50 ? 'warn' : 'bad')
const BAR = { ok: 'bg-ok', warn: 'bg-warn', bad: 'bg-bad' }

export function ConfidenceBar({ value }) {
  const tone = confTone(value)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-800">
        <div className={`h-full rounded-full ${BAR[tone]}`} style={{ width: `${value}%` }} />
      </div>
      <span className={`w-24 whitespace-nowrap text-right font-mono text-xs ${tone === 'ok' ? 'text-ok' : tone === 'warn' ? 'text-warn' : 'text-bad'}`}>
        {value}% match
      </span>
    </div>
  )
}

export function Cite({ id }) {
  const { open } = useContext(RecordContext)
  const isMop = id.startsWith('MOP')
  return (
    <button
      onClick={() => !isMop && open(id)}
      className="mx-0.5 inline-flex items-center rounded border border-info/40 bg-info/10 px-1 font-mono text-[11px] text-info hover:bg-info/20"
      title={isMop ? 'MOP reference' : 'Open source record'}
    >
      {id}
    </button>
  )
}

/** Render text, turning "[LNI-1, LNI-2]" citations into clickable chips. */
export function Cited({ text }) {
  const parts = text.split(/\[([^\]]+)\]/g)
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <span key={i} className="whitespace-nowrap">
            {p.split(/\s*[,;]\s*/).map((id) => <Cite key={id} id={id.trim()} />)}
          </span>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-300">
        {label} {hint && <span className="text-ink-500">· {hint}</span>}
      </span>
      {children}
    </label>
  )
}

export const inputCls =
  'w-full rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-amber/70 focus:outline-none'

export function Spinner() {
  return <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink-500 border-t-amber" />
}

export function Empty({ children }) {
  return <p className="py-6 text-center text-sm text-ink-500">{children}</p>
}

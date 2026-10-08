import { createContext, useContext } from 'react'

export const RecordContext = createContext({ open: () => {} })

/** "2026-10-09T01:40:12+05:30" -> "9 Oct 2026, 01:40" (shown in the viewer's local time). */
export function formatTs(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function Card({ title, icon: Icon, right, children, className = '', bodyClass = 'p-5', subtitle }) {
  return (
    <section className={`rounded-xl border border-line bg-surface shadow-card ${className}`}>
      {(title || right) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
          <div className="flex min-w-0 items-center gap-2.5">
            {Icon && <Icon size={17} className="shrink-0 text-subtle" />}
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-fg">{title}</h3>
              {subtitle && <p className="truncate text-xs text-subtle">{subtitle}</p>}
            </div>
          </div>
          {right}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

const BTN = {
  primary: 'bg-accent text-[#1a1200] shadow-card hover:brightness-105 active:brightness-95',
  secondary: 'border border-line-strong bg-surface text-fg shadow-card hover:bg-surface-2',
  ghost: 'text-muted hover:bg-surface-3 hover:text-fg',
  ok: 'border border-ok/40 bg-ok/10 text-ok hover:bg-ok/15',
  link: 'border border-link/30 bg-link/10 text-link hover:bg-link/15',
}
const SIZE = { sm: 'h-8 px-3 text-xs gap-1.5', md: 'h-10 px-4 text-sm gap-2', lg: 'h-11 px-5 text-sm gap-2' }

export function Button({ children, variant = 'primary', size = 'md', icon: Icon, className = '', ...props }) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-lg font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${SIZE[size]} ${BTN[variant]} ${className}`}
      {...props}
    >
      {Icon && <Icon size={size === 'sm' ? 14 : 16} />}
      {children}
    </button>
  )
}

const TONES = {
  neutral: 'border-line bg-surface-2 text-muted',
  accent: 'border-accent/40 bg-accent/12 text-accent-ink',
  link: 'border-link/30 bg-link/10 text-link',
  ok: 'border-ok/30 bg-ok/10 text-ok',
  warn: 'border-warn/30 bg-warn/10 text-warn',
  bad: 'border-bad/30 bg-bad/10 text-bad',
}

export function Badge({ tone = 'neutral', icon: Icon, children, className = '', title }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-medium ${TONES[tone]} ${className}`}>
      {Icon && <Icon size={12} />}
      {children}
    </span>
  )
}

export const OUTCOME_TONE = { outage: 'bad', rollback: 'bad', 'service degraded': 'warn', resolved: 'ok', success: 'neutral' }
export const outcomeTone = (o) => OUTCOME_TONE[(o || '').toLowerCase()] || 'neutral'

export const confTone = (v) => (v >= 80 ? 'ok' : v >= 50 ? 'warn' : 'bad')
export const confWord = (v) => (v >= 80 ? 'Strong match' : v >= 50 ? 'Possible match' : 'Weak - not used')
const RING = { ok: 'var(--ok)', warn: 'var(--warn)', bad: 'var(--bad)' }

/** Circular confidence gauge with the % in the middle. */
export function ConfidenceRing({ value, size = 52 }) {
  const r = (size - 6) / 2
  const c = 2 * Math.PI * r
  const tone = confTone(value)
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title={`${value}% match - ${confWord(value)}`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth="5" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={RING[tone]} strokeWidth="5" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[13px] font-bold text-fg">{value}%</span>
    </div>
  )
}

export function Cite({ id }) {
  const { open } = useContext(RecordContext)
  const isMop = id.startsWith('MOP')
  return (
    <button
      onClick={(e) => { e.stopPropagation(); if (!isMop) open(id) }}
      className={`mx-0.5 inline-flex items-center rounded-md border px-1.5 align-baseline font-mono text-[11px] leading-5 transition ${isMop ? 'cursor-default border-line bg-surface-2 text-muted' : 'border-link/25 bg-link/8 text-link hover:border-link/50 hover:bg-link/15'}`}
      title={isMop ? 'MOP reference' : 'Open the source record (proof)'}
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

export function Field({ label, hint, error, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline gap-2 text-[13px] font-medium text-fg">
        {label} {hint && <span className="text-xs font-normal text-subtle">{hint}</span>}
      </span>
      {children}
      {error && <span className="mt-1 block text-xs text-bad">{error}</span>}
    </label>
  )
}

export const inputCls =
  'w-full rounded-lg border border-line-strong bg-surface px-3 py-2.5 text-sm text-fg placeholder:text-subtle shadow-card transition focus:border-link focus:outline-none focus:ring-3 focus:ring-link/15'

export function Spinner({ className = '' }) {
  return <span className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-accent ${className}`} />
}

export function Skeleton({ className = '' }) {
  return <div className={`skeleton ${className}`} />
}

export function Empty({ icon: Icon, title, children }) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      {Icon && <div className="mb-3 rounded-full bg-surface-3 p-3 text-subtle"><Icon size={22} /></div>}
      {title && <p className="text-sm font-semibold text-fg">{title}</p>}
      {children && <p className="mt-1 max-w-sm text-sm text-subtle">{children}</p>}
    </div>
  )
}

/** Small hover tooltip. */
export function Tip({ text, children, className = '' }) {
  return (
    <span className={`group relative inline-flex ${className}`}>
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 z-40 mb-2 w-max max-w-64 -translate-x-1/2 rounded-md bg-fg px-2.5 py-1.5 text-[11px] leading-snug font-normal text-bg opacity-0 shadow-pop transition group-hover:opacity-100">
        {text}
      </span>
    </span>
  )
}

/** Segmented tab control: tabs = [{ id, label, icon, count }]. */
export function Segmented({ tabs, value, onChange }) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-lg bg-surface-3 p-1">
      {tabs.map(({ id, label, icon: Icon, count }) => (
        <button key={id} onClick={() => onChange(id)}
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition ${value === id ? 'bg-surface text-fg shadow-card' : 'text-muted hover:text-fg'}`}>
          {Icon && <Icon size={14} />}
          {label}
          {count != null && <span className={`rounded px-1.5 text-[11px] ${value === id ? 'bg-surface-3 text-muted' : 'bg-surface text-subtle'}`}>{count}</span>}
        </button>
      ))}
    </div>
  )
}

export function Kbd({ children }) {
  return <kbd className="rounded border border-line-strong bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">{children}</kbd>
}

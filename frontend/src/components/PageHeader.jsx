import { useState } from 'react'
import { ChevronDown, Lightbulb } from 'lucide-react'

function readOpen(key) {
  try { return localStorage.getItem(`lni-hints-${key}`) !== 'closed' } catch { return true }
}

/** Page title + one-line purpose + a collapsible "How to use this page" strip (remembered per page). */
export default function PageHeader({ icon: Icon, eyebrow, title, purpose, hints = [], id }) {
  const [open, setOpen] = useState(() => readOpen(id))
  const toggle = () => {
    setOpen(!open)
    try { localStorage.setItem(`lni-hints-${id}`, open ? 'closed' : 'open') } catch { /* storage blocked */ }
  }
  return (
    <div className="mb-6">
      <div className="flex items-start gap-4">
        {Icon && (
          <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line bg-surface text-accent-ink shadow-card sm:flex">
            <Icon size={22} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          {eyebrow && <p className="text-xs font-semibold tracking-wide text-accent-ink uppercase">{eyebrow}</p>}
          <h1 className="text-2xl font-bold tracking-tight text-fg">{title}</h1>
          {purpose && <p className="mt-1 max-w-3xl text-[15px] text-muted">{purpose}</p>}
        </div>
      </div>
      {hints.length > 0 && (
        <div className="mt-4 rounded-xl border border-line bg-surface-2">
          <button onClick={toggle} className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[13px] font-semibold text-fg">
            <Lightbulb size={15} className="text-accent-ink" /> How to use this page
            <ChevronDown size={16} className={`ml-auto text-subtle transition-transform ${open ? 'rotate-180' : ''}`} />
          </button>
          <div className="reveal" data-open={open}>
            <div>
              <ol className="grid gap-3 px-4 pb-4 sm:grid-cols-3">
                {hints.map((h, i) => (
                  <li key={i} className="flex gap-2.5 text-[13px] text-muted">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/15 text-[11px] font-bold text-accent-ink">{i + 1}</span>
                    <span>{h}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

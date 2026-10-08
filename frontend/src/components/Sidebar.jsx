import { BookmarkCheck, ExternalLink, House, Library, Moon, Network, ShieldAlert, Siren, Sun, TrendingUp, X } from 'lucide-react'
import { API } from '../api'
import { Tip } from './ui'

export const NAV = [
  { id: 'home', label: 'Home', sub: 'What this app does', icon: House },
  { id: 'plan', label: 'Plan a change', sub: 'Before · get warnings', icon: ShieldAlert, group: 'The 3 moments' },
  { id: 'incident', label: 'Fix an incident', sub: 'During · find the old fix', icon: Siren },
  { id: 'save', label: 'Save a lesson', sub: 'After · remember the fix', icon: BookmarkCheck },
  { id: 'kb', label: 'Knowledge base', sub: 'Browse all past records', icon: Library, group: 'Explore' },
  { id: 'trends', label: 'Trends', sub: 'Problems that repeat', icon: TrendingUp },
]

function Status({ health, down }) {
  if (down) {
    return (
      <div className="rounded-lg border border-bad/30 bg-bad/10 p-2.5 text-xs text-bad">
        <b>Backend not running.</b> Start it on {API.replace('http://', '')}.
      </div>
    )
  }
  if (!health) return <p className="text-xs text-subtle">Connecting…</p>
  const ai = health.llm.available
  return (
    <div className="space-y-1.5 text-xs">
      <p className="flex items-center gap-2 text-muted">
        <span className="h-2 w-2 rounded-full bg-ok" /> Connected
      </p>
      <p className="text-muted"><b className="text-fg">{health.records}</b> past tickets{health.mops > 0 && <> · <b className="text-fg">{health.mops}</b> MOPs</>}</p>
      <p className="text-muted"><b className="text-fg">{health.learnings}</b> verified lesson{health.learnings === 1 ? '' : 's'} saved</p>
      <Tip text={ai ? `Answers are rewritten by ${health.llm.model}; every line is still checked for proof.`
        : 'No AI writer running. Answers are built directly from past records, so they are always correct and cited.'}>
        <p className="flex cursor-help items-center gap-2 text-muted">
          <span className={`h-2 w-2 rounded-full ${ai ? 'bg-link' : 'bg-line-strong'}`} />
          AI writer: <b className="text-fg">{ai ? `on (${health.llm.model})` : 'off'}</b>
        </p>
      </Tip>
    </div>
  )
}

export default function Sidebar({ route, onNavigate, health, down, theme, onToggleTheme, mobileOpen, onClose }) {
  const body = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-5 pt-5 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-[#1a1200] shadow-card"><Network size={19} /></div>
        <div className="min-w-0">
          <p className="text-sm leading-tight font-bold text-fg">LNI Learning Agent</p>
          <p className="text-[11px] text-subtle">Incident learning &amp; prevention</p>
        </div>
        {mobileOpen && <button onClick={onClose} className="ml-auto text-subtle hover:text-fg lg:hidden" aria-label="Close menu"><X size={18} /></button>}
      </div>
      <nav className="scroll-thin flex-1 space-y-0.5 overflow-y-auto px-3">
        {NAV.map(({ id, label, sub, icon: Icon, group }) => (
          <div key={id}>
            {group && <p className="px-3 pt-4 pb-1.5 text-[11px] font-semibold tracking-wide text-subtle uppercase">{group}</p>}
            <button onClick={() => onNavigate(id)}
              className={`group relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition ${route === id ? 'bg-accent/12 text-fg' : 'text-muted hover:bg-surface-3 hover:text-fg'}`}>
              {route === id && <span className="absolute top-2 bottom-2 left-0 w-[3px] rounded-r bg-accent" />}
              <Icon size={18} className={route === id ? 'text-accent-ink' : 'text-subtle group-hover:text-muted'} />
              <span className="min-w-0">
                <span className="block text-sm font-medium">{label}</span>
                <span className="block truncate text-[11px] text-subtle">{sub}</span>
              </span>
            </button>
          </div>
        ))}
      </nav>
      <div className="space-y-3 border-t border-line px-5 py-4">
        <Status health={health} down={down} />
        <div className="flex items-center justify-between">
          <button onClick={onToggleTheme}
            className="inline-flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-muted transition hover:bg-surface-3 hover:text-fg">
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>
          <a href={`${API}/docs`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-link hover:underline">
            API docs <ExternalLink size={12} />
          </a>
        </div>
      </div>
    </div>
  )

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-line bg-surface lg:block">{body}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="animate-fade-in absolute inset-0 bg-black/40" onClick={onClose} />
          <aside className="animate-sidebar absolute inset-y-0 left-0 w-72 border-r border-line bg-surface shadow-pop">{body}</aside>
        </div>
      )}
    </>
  )
}

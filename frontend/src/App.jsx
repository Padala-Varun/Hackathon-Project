import { useCallback, useEffect, useMemo, useState } from 'react'
import { Menu, Moon, Network, Sun } from 'lucide-react'
import { api, API } from './api'
import Home from './components/Home'
import Incident from './components/Incident'
import KnowledgeBase from './components/KnowledgeBase'
import PreChange, { PLAN_EXAMPLES } from './components/PreChange'
import RecordDrawer from './components/RecordDrawer'
import Sidebar, { NAV } from './components/Sidebar'
import { ToastProvider } from './components/Toast'
import Trends from './components/Trends'
import WriteBack from './components/WriteBack'
import { RecordContext } from './components/ui'

const ROUTES = NAV.map((n) => n.id)
const routeFromHash = () => {
  const m = window.location.hash.match(/^#\/(\w+)/)
  return m && ROUTES.includes(m[1]) ? m[1] : 'home'
}

export default function App() {
  const [route, setRoute] = useState(routeFromHash)
  const [health, setHealth] = useState(null)
  const [down, setDown] = useState(false)
  const [nodes, setNodes] = useState([])
  const [mops, setMops] = useState([])
  const [products, setProducts] = useState([])
  const [record, setRecord] = useState(null)
  const [prefill, setPrefill] = useState({})
  const [menuOpen, setMenuOpen] = useState(false)
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light')

  const loadHealth = useCallback(() => api.health().then((h) => { setHealth(h); setDown(false) }).catch(() => setDown(true)), [])

  useEffect(() => {
    loadHealth()
    api.nodes().then(setNodes).catch(() => {})
    api.mops().then(setMops).catch(() => {})
    api.products().then(setProducts).catch(() => {})
    const t = setInterval(loadHealth, 15000)
    const onHash = () => setRoute(routeFromHash())
    window.addEventListener('hashchange', onHash)
    // #demo = one-click demo of the brief's sample scenario
    if (window.location.hash === '#demo') {
      window.history.replaceState(null, '', '#/plan')
      setRoute('plan')
      setPrefill({ plan: { text: PLAN_EXAMPLES[0].text, autorun: true, at: Date.now() } })
    }
    return () => { clearInterval(t); window.removeEventListener('hashchange', onHash) }
  }, [loadHealth])

  const navigate = useCallback((to, data) => {
    if (data) setPrefill((p) => ({ ...p, [to]: { ...data, at: Date.now() } }))
    setMenuOpen(false)
    if (routeFromHash() !== to) window.location.hash = `#/${to}`
    setRoute(to)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('lni-theme', next) } catch { /* storage blocked */ }
    setTheme(next)
  }

  const ctx = useMemo(() => ({ open: setRecord }), [])
  const page = (id) => (route === id ? 'animate-fade-in' : 'hidden')

  return (
    <ToastProvider>
      <RecordContext.Provider value={ctx}>
        <Sidebar route={route} onNavigate={navigate} health={health} down={down} theme={theme} onToggleTheme={toggleTheme}
          mobileOpen={menuOpen} onClose={() => setMenuOpen(false)} />
        <div className="lg:pl-64">
          <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-surface/90 px-4 py-3 backdrop-blur lg:hidden">
            <button onClick={() => setMenuOpen(true)} className="rounded-md p-1.5 text-muted hover:bg-surface-3" aria-label="Open menu"><Menu size={20} /></button>
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent text-[#1a1200]"><Network size={15} /></div>
            <span className="text-sm font-bold text-fg">LNI Learning Agent</span>
            <button onClick={toggleTheme} className="ml-auto rounded-md p-1.5 text-muted hover:bg-surface-3" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </header>
          {down && (
            <div className="border-b border-bad/30 bg-bad/10 px-6 py-2.5 text-center text-sm text-bad">
              The backend is not running. Start it with <code className="font-mono">uvicorn app.main:app --port 8000</code> ({API}).
            </div>
          )}
          <main className="mx-auto max-w-[1360px] px-4 py-6 sm:px-8 sm:py-8">
            <div className={page('home')}><Home health={health} products={products} onNavigate={navigate} /></div>
            <div className={page('plan')}><PreChange nodes={nodes} mops={mops} products={products} prefill={prefill.plan} /></div>
            <div className={page('incident')}>
              <Incident nodes={nodes} products={products} prefill={prefill.incident} onWriteBack={(d) => navigate('save', d)} />
            </div>
            <div className={page('save')}>
              <WriteBack draft={prefill.save} onSaved={loadHealth} onFindNow={(text) => navigate('incident', { text, autorun: true })} />
            </div>
            {route === 'kb' && <div className="animate-fade-in"><KnowledgeBase onChanged={loadHealth} /></div>}
            {route === 'trends' && <div className="animate-fade-in"><Trends /></div>}
          </main>
        </div>
        {record && <RecordDrawer id={record} onClose={() => setRecord(null)} />}
      </RecordContext.Provider>
    </ToastProvider>
  )
}

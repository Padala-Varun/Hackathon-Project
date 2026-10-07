import { useEffect, useMemo, useState } from 'react'
import { api, API } from './api'
import Incident from './components/Incident'
import KnowledgeBase from './components/KnowledgeBase'
import PreChange from './components/PreChange'
import RecordModal from './components/RecordModal'
import Trends from './components/Trends'
import WriteBack from './components/WriteBack'
import { Pill, RecordContext } from './components/ui'

const TABS = [
  ['pre', 'Before · Pre-change check'],
  ['incident', 'During · Incident assistant'],
  ['writeback', 'After · Write back learning'],
  ['kb', 'Knowledge base'],
  ['trends', 'Trends'],
]

export default function App() {
  const [tab, setTab] = useState('pre')
  const [health, setHealth] = useState(null)
  const [down, setDown] = useState(false)
  const [nodes, setNodes] = useState([])
  const [mops, setMops] = useState([])
  const [record, setRecord] = useState(null)
  const [draft, setDraft] = useState(null)

  useEffect(() => {
    const load = () =>
      api.health().then((h) => { setHealth(h); setDown(false) }).catch(() => setDown(true))
    load()
    api.nodes().then(setNodes).catch(() => {})
    api.mops().then(setMops).catch(() => {})
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [])

  const ctx = useMemo(() => ({ open: setRecord }), [])

  return (
    <RecordContext.Provider value={ctx}>
      <div className="min-h-full">
        <header className="border-b border-ink-800 bg-ink-900/80 backdrop-blur">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-amber">AI Incident Learning &amp; Prevention Agent</p>
              <h1 className="text-lg font-bold text-ink-100">Institutional memory for every LNI</h1>
            </div>
            <div className="ml-auto flex flex-wrap items-center gap-2 text-xs">
              {down && <Pill tone="bad">API offline · start the backend on {API}</Pill>}
              {health && (
                <>
                  <Pill>{health.records} LNIs · {health.mops} MOPs · {health.logs} logs</Pill>
                  <Pill tone="ok">{health.learnings} verified learnings</Pill>
                  <Pill tone={health.llm.available ? 'info' : 'dim'}>
                    LLM {health.llm.model}: {health.llm.available ? 'online' : 'offline (cited template mode)'}
                  </Pill>
                  <Pill tone="dim">rerank {health.reranker?.split('/').pop() || 'off'}</Pill>
                  <a className="text-info hover:underline" href={`${API}/docs`} target="_blank" rel="noreferrer">API docs ↗</a>
                </>
              )}
            </div>
          </div>
          <nav className="mx-auto flex max-w-[1400px] gap-1 overflow-x-auto px-5">
            {TABS.map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)}
                className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition ${tab === id ? 'border-amber text-ink-100' : 'border-transparent text-ink-500 hover:text-ink-300'}`}>
                {label}
              </button>
            ))}
          </nav>
        </header>
        <main className="mx-auto max-w-[1400px] px-5 py-6">
          <div className={tab === 'pre' ? '' : 'hidden'}><PreChange nodes={nodes} mops={mops} /></div>
          <div className={tab === 'incident' ? '' : 'hidden'}>
            <Incident nodes={nodes} onWriteBack={(d) => { setDraft({ ...d, at: Date.now() }); setTab('writeback') }} />
          </div>
          <div className={tab === 'writeback' ? '' : 'hidden'}><WriteBack draft={draft} /></div>
          {tab === 'kb' && <KnowledgeBase />}
          {tab === 'trends' && <Trends />}
        </main>
        <footer className="mx-auto max-w-[1400px] px-5 pb-6 text-[11px] text-ink-500">
          Read-only agent: it surfaces verified, cited history - the engineer decides. Synthetic data only.
        </footer>
      </div>
      {record && <RecordModal id={record} onClose={() => setRecord(null)} />}
    </RecordContext.Provider>
  )
}

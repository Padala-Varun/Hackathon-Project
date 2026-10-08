import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { BellRing, CircleAlert, CircleCheck, Info, X } from 'lucide-react'

const ToastContext = createContext({ push: () => {} })
export const useToast = () => useContext(ToastContext)

const STYLE = {
  ok: ['text-ok', CircleCheck],
  info: ['text-link', Info],
  warn: ['text-warn', BellRing],
  bad: ['text-bad', CircleAlert],
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const push = useCallback((toast) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t.slice(-3), { id, tone: 'ok', ...toast }])
    setTimeout(() => dismiss(id), toast.duration || 5000)
  }, [dismiss])
  const value = useMemo(() => ({ push }), [push])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((t) => {
          const [color, Icon] = STYLE[t.tone] || STYLE.info
          return (
            <div key={t.id} role="status" className="animate-toast pointer-events-auto flex gap-3 rounded-xl border border-line bg-surface p-3.5 shadow-pop">
              <Icon size={18} className={`mt-0.5 shrink-0 ${color}`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-fg">{t.title}</p>
                {t.body && <p className="mt-0.5 text-[13px] text-muted">{t.body}</p>}
                {t.action && (
                  <button className="mt-1.5 text-[13px] font-semibold text-link hover:underline" onClick={() => { t.action.onClick(); dismiss(t.id) }}>
                    {t.action.label}
                  </button>
                )}
              </div>
              <button onClick={() => dismiss(t.id)} className="self-start text-subtle hover:text-fg" aria-label="Dismiss"><X size={16} /></button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

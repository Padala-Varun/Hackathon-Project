import { useRef, useState } from 'react'
import { streamRecommend } from '../api'

/** Runs the agent via SSE and exposes the live trace, streamed LLM text and the final recommendation. */
export function useAgentRun() {
  const [events, setEvents] = useState([])
  const [llmText, setLlmText] = useState('')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [runId, setRunId] = useState(0)
  const abortRef = useRef(null)

  async function run(body) {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setEvents([])
    setLlmText('')
    setResult(null)
    setError('')
    setRunId((n) => n + 1)
    setRunning(true)
    try {
      await streamRecommend(
        body,
        (ev) => {
          if (abortRef.current !== ctrl) return // a newer run replaced this one
          if (ev.type === 'llm_token') setLlmText((t) => t + ev.message)
          else if (ev.type === 'final') setResult(ev.data.recommendation)
          else setEvents((e) => [...e, ev])
        },
        ctrl.signal,
      )
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message || String(e))
    } finally {
      if (abortRef.current === ctrl) setRunning(false)
    }
  }

  return { events, llmText, result, running, error, run, runId }
}

import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface DemoEvent {
  type: string
  phase?: string
  event?: string
  text?: string
  label?: string
  confidence?: number
  action?: string
  latency_ms?: number
  expected?: string
  predicted?: string
  corrected_to?: string
  similar_matches?: number
  message?: string
}

interface DemoState {
  running: boolean
  events: DemoEvent[]
  phase: string
  report: Record<string, unknown> | null
}

const ACTION_COLORS: Record<string, string> = {
  allow: 'text-green-400 border-green-800 bg-green-950',
  block: 'text-red-400 border-red-800 bg-red-950',
  flag: 'text-yellow-400 border-yellow-800 bg-yellow-950',
}

export function DemoPanel() {
  const [state, setState] = useState<DemoState>({
    running: false,
    events: [],
    phase: '',
    report: null,
  })
  const wsRef = useRef<WebSocket | null>(null)
  const feedRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.hostname}:8000/api/v1/stream/ws`)
    wsRef.current = ws

    ws.onmessage = (e) => {
      const data: DemoEvent = JSON.parse(e.data)
      if (data.type !== 'demo') return

      setState((prev) => {
        const events = [data, ...prev.events].slice(0, 60)
        let report = prev.report
        if (data.event === 'done') {
          report = (data as { report?: Record<string, unknown> }).report ?? null
        }
        return {
          running: data.event !== 'done' && data.event !== 'error',
          events,
          phase: data.phase ?? prev.phase,
          report,
        }
      })
    }

    return () => ws.close()
  }, [])

  const runDemo = async () => {
    setState({ running: true, events: [], phase: 'Starting…', report: null })
    try {
      await fetch('/api/v1/demo/run', { method: 'POST' })
    } catch {
      setState((prev) => ({ ...prev, running: false }))
    }
  }

  const r = state.report as {
    total_requests?: number
    blocked?: number
    allowed?: number
    alerts_fired?: string[]
    feedback_applied?: number
    retrain_metrics?: { accuracy?: number; f1_macro?: number }
    duration_sec?: number
    phase_log?: string[]
  } | null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Live Demo</h2>
          <p className="text-xs text-zinc-500">
            Orchestrated scenario: traffic → spike → alerts → feedback → retrain
          </p>
        </div>
        <button
          onClick={runDemo}
          disabled={state.running}
          className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
            state.running
              ? 'border-zinc-700 bg-zinc-800 text-zinc-500'
              : 'border-blue-700 bg-blue-950 text-blue-400 hover:bg-blue-900'
          }`}
        >
          {state.running ? '⏳ Running…' : '▶ Run Demo'}
        </button>
      </div>

      {/* Current phase */}
      {state.phase && (
        <div className="rounded-lg border border-blue-900/50 bg-blue-950/30 px-4 py-2 text-sm text-blue-300">
          {state.running && (
            <motion.span
              className="mr-2 inline-block"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
            >
              ●
            </motion.span>
          )}
          {state.phase}
        </div>
      )}

      {/* Final report */}
      <AnimatePresence>
        {r && !state.running && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4"
          >
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
              Demo Report — completed in {r.duration_sec}s
            </h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {[
                { label: 'Requests', value: r.total_requests ?? 0, color: 'text-zinc-200' },
                { label: 'Blocked', value: r.blocked ?? 0, color: 'text-red-400' },
                { label: 'Allowed', value: r.allowed ?? 0, color: 'text-green-400' },
                { label: 'Alerts', value: (r.alerts_fired ?? []).length, color: 'text-yellow-400' },
                { label: 'Feedback', value: r.feedback_applied ?? 0, color: 'text-blue-400' },
              ].map((kpi) => (
                <div key={kpi.label} className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-center">
                  <div className={`text-2xl font-bold ${kpi.color}`}>{kpi.value}</div>
                  <div className="text-xs uppercase tracking-wider text-zinc-600">{kpi.label}</div>
                </div>
              ))}
            </div>
            {r.retrain_metrics?.accuracy !== undefined && (
              <div className="mt-3 rounded-lg border border-green-900/50 bg-green-950/30 px-4 py-2 text-sm text-green-300">
                🧠 Retrained model: accuracy {(Number(r.retrain_metrics.accuracy) * 100).toFixed(1)}%
                {r.retrain_metrics.f1_macro !== undefined &&
                  `, F1-macro ${(Number(r.retrain_metrics.f1_macro) * 100).toFixed(1)}%`}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Live event feed */}
      <div
        ref={feedRef}
        className="max-h-[450px] space-y-1.5 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900/30 p-3"
      >
        {state.events.length === 0 ? (
          <p className="py-8 text-center text-sm text-zinc-600">
            Click "Run Demo" to start the orchestrated scenario
          </p>
        ) : (
          state.events.map((e, i) => (
            <DemoEventRow key={i} event={e} />
          ))
        )}
      </div>
    </div>
  )
}

function DemoEventRow({ event }: { event: DemoEvent }) {
  // Phase marker
  if (event.phase) {
    return (
      <div className="my-2 flex items-center gap-2">
        <div className="h-px flex-1 bg-zinc-800" />
        <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">
          {event.phase}
        </span>
        <div className="h-px flex-1 bg-zinc-800" />
      </div>
    )
  }

  if (event.event === 'error') {
    return (
      <div className="rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-400">
        ❌ {event.message}
      </div>
    )
  }

  if (event.event === 'prediction' || event.event === 'filter') {
    const match = event.expected && event.label === event.expected
    return (
      <div
        className={`flex items-center justify-between rounded-lg border px-3 py-1.5 ${
          ACTION_COLORS[event.action ?? 'allow'] ?? 'border-zinc-800 bg-zinc-900'
        }`}
      >
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-xs font-bold uppercase">{event.action}</span>
          <span className="truncate text-sm text-zinc-300">{event.text}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs text-zinc-500">
          {event.expected && (
            <span className={match ? 'text-green-500' : 'text-orange-500'}>
              {match ? '✓' : '✗ exp:' + event.expected}
            </span>
          )}
          <span>{event.label} {Math.round((event.confidence ?? 0) * 100)}%</span>
          <span>{(event.latency_ms ?? 0).toFixed(1)}ms</span>
          {event.similar_matches !== undefined && event.similar_matches > 0 && (
            <span className="text-blue-400">🔗{event.similar_matches}</span>
          )}
        </div>
      </div>
    )
  }

  if (event.event === 'feedback') {
    return (
      <div className="flex items-center justify-between rounded-lg border border-blue-800 bg-blue-950 px-3 py-1.5 text-sm">
        <span className="truncate text-blue-200">👤 {event.text}</span>
        <span className="shrink-0 text-xs text-zinc-400">
          {event.predicted} → <span className="text-green-400">{event.corrected_to}</span>
        </span>
      </div>
    )
  }

  return null
}

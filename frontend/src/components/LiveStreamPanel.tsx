import { useState, useEffect, useRef, useCallback } from 'react'

interface ModerationEvent {
  type: string
  text: string
  label: string
  confidence: number
  action: string
  latency_ms: number
  timestamp: number
  expected?: string
}

const ACTION_COLORS: Record<string, string> = {
  allow: 'text-green-400 border-green-800 bg-green-950',
  block: 'text-red-400 border-red-800 bg-red-950',
  flag: 'text-yellow-400 border-yellow-800 bg-yellow-950',
}

const LABEL_COLORS: Record<string, string> = {
  safe: 'text-green-400',
  spam: 'text-red-400',
  toxic: 'text-orange-400',
}

export function LiveStreamPanel() {
  const [connected, setConnected] = useState(false)
  const [simRunning, setSimRunning] = useState(false)
  const [events, setEvents] = useState<ModerationEvent[]>([])
  const [stats, setStats] = useState({ total: 0, allow: 0, block: 0 })
  const [input, setInput] = useState('')
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.hostname}:8000/api/v1/stream/ws`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      setSimRunning(false)
    }
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'moderation') {
        setEvents((prev) => [data, ...prev].slice(0, 50))
        setStats((prev) => ({
          total: prev.total + 1,
          allow: prev.allow + (data.action === 'allow' ? 1 : 0),
          block: prev.block + (data.action === 'block' ? 1 : 0),
        }))
      }
    }
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  const toggleSimulator = async () => {
    const action = simRunning ? 'stop' : 'start'
    try {
      await fetch(`/api/v1/stream/simulator/${action}`, { method: 'POST' })
      setSimRunning(!simRunning)
    } catch {
      // ignore
    }
  }

  const sendCustom = () => {
    if (!input.trim() || !connected) return
    wsRef.current?.send(JSON.stringify({ type: 'moderate', text: input }))
    setInput('')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Live Moderation Stream</h2>
          <p className="text-xs text-zinc-500">
            Real-time WebSocket feed · {connected ? (
              <span className="text-green-400">● Connected</span>
            ) : (
              <span className="text-red-400">● Disconnected</span>
            )}
          </p>
        </div>
        <button
          onClick={toggleSimulator}
          className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
            simRunning
              ? 'border-red-800 bg-red-950 text-red-400 hover:bg-red-900'
              : 'border-blue-700 bg-blue-950 text-blue-400 hover:bg-blue-900'
          }`}
        >
          {simRunning ? '⏹ Stop Simulator' : '▶ Start Simulator'}
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total', value: stats.total, color: 'text-zinc-200' },
          { label: 'Allowed', value: stats.allow, color: 'text-green-400' },
          { label: 'Blocked', value: stats.block, color: 'text-red-400' },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3 text-center">
            <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-xs uppercase tracking-wider text-zinc-500">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Custom message input */}
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendCustom()}
          placeholder="Send a message to moderate..."
          className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none"
        />
        <button
          onClick={sendCustom}
          disabled={!connected || !input.trim()}
          className="rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-700 disabled:opacity-40"
        >
          Send →
        </button>
      </div>

      {/* Live feed */}
      <div className="max-h-[500px] space-y-2 overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
        {events.length === 0 ? (
          <p className="py-8 text-center text-sm text-zinc-600">
            No events yet. Start the simulator or send a message.
          </p>
        ) : (
          events.map((e, i) => (
            <div
              key={i}
              className={`flex items-center justify-between rounded-lg border px-3 py-2 ${
                ACTION_COLORS[e.action] ?? 'border-zinc-800 bg-zinc-900'
              } ${i === 0 ? 'ring-1 ring-zinc-600' : ''}`}
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${ACTION_COLORS[e.action]}`}>
                  {e.action}
                </span>
                <span className="truncate text-sm text-zinc-300">{e.text}</span>
              </div>
              <div className="flex shrink-0 items-center gap-2 text-xs text-zinc-500">
                <span className={LABEL_COLORS[e.label] ?? 'text-zinc-400'}>
                  {e.label} {Math.round(e.confidence * 100)}%
                </span>
                <span>{e.latency_ms.toFixed(1)}ms</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

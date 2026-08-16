import { useState, useEffect } from 'react'

interface Alert {
  type: string
  severity: string
  message: string
  value: number
  threshold: number
  timestamp: string
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'border-red-800 bg-red-950 text-red-400',
  warning: 'border-yellow-800 bg-yellow-950 text-yellow-400',
  info: 'border-blue-800 bg-blue-950 text-blue-400',
}

export function AlertPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [thresholds, setThresholds] = useState<Record<string, number>>({})
  const [webhooks, setWebhooks] = useState<Record<string, unknown>[]>([])
  const [whUrl, setWhUrl] = useState('')
  const [whName, setWhName] = useState('')

  const load = async () => {
    try {
      const [hRes, tRes, wRes] = await Promise.all([
        fetch('/api/v1/alerts/history?limit=20'),
        fetch('/api/v1/alerts/thresholds'),
        fetch('/api/v1/alerts/webhooks'),
      ])
      setAlerts((await hRes.json()).alerts || [])
      setThresholds(await tRes.json())
      setWebhooks((await wRes.json()).webhooks || [])
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [])

  const addWebhook = async () => {
    if (!whUrl.trim()) return
    await fetch('/api/v1/alerts/webhooks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: whUrl, name: whName || 'default' }),
    })
    setWhUrl('')
    setWhName('')
    load()
  }

  const removeWebhook = async (name: string) => {
    await fetch(`/api/v1/alerts/webhooks/${name}`, { method: 'DELETE' })
    load()
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="mb-1 text-lg font-semibold text-zinc-100">Alerting System</h2>
        <p className="text-xs text-zinc-500">
          Automated alerts for toxicity spikes, drift, latency anomalies
        </p>
      </div>

      {/* Thresholds */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Thresholds
        </h3>
        <div className="grid grid-cols-3 gap-3">
          {Object.entries(thresholds).filter(([k]) => k !== 'min_window_size').map(([key, val]) => (
            <div key={key} className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-center">
              <div className="text-lg font-bold text-zinc-200">
                {typeof val === 'number' && val < 1 ? val : val}
              </div>
              <div className="text-xs text-zinc-500">{key.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Webhooks */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Notification Webhooks ({webhooks.length})
        </h3>
        <div className="mb-3 space-y-2">
          {webhooks.length === 0 ? (
            <p className="text-xs text-zinc-600">No webhooks configured</p>
          ) : (
            webhooks.map((w: Record<string, unknown>, i: number) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2">
                <div className="min-w-0">
                  <span className="text-sm text-zinc-300">{w.name as string}</span>
                  <span className="ml-2 truncate text-xs text-zinc-600">{(w.url as string)?.substring(0, 50)}…</span>
                </div>
                <button
                  onClick={() => removeWebhook(w.name as string)}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  Remove
                </button>
              </div>
            ))
          )}
        </div>
        <div className="flex gap-2">
          <input
            value={whName}
            onChange={(e) => setWhName(e.target.value)}
            placeholder="Name"
            className="w-24 rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-1.5 text-xs text-zinc-200"
          />
          <input
            value={whUrl}
            onChange={(e) => setWhUrl(e.target.value)}
            placeholder="https://hooks.slack.com/... or Telegram bot URL"
            className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-1.5 text-xs text-zinc-200"
          />
          <button
            onClick={addWebhook}
            className="rounded-lg border border-blue-700 bg-blue-950 px-3 py-1.5 text-xs text-blue-400 hover:bg-blue-900"
          >
            Add
          </button>
        </div>
      </div>

      {/* Alert History */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Recent Alerts ({alerts.length})
        </h3>
        {alerts.length === 0 ? (
          <p className="py-4 text-center text-sm text-zinc-600">No alerts. System is healthy.</p>
        ) : (
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {alerts.slice().reverse().map((a, i) => (
              <div
                key={i}
                className={`flex items-center justify-between rounded-lg border px-3 py-2 ${
                  SEVERITY_STYLES[a.severity] ?? 'border-zinc-800 bg-zinc-900'
                }`}
              >
                <div>
                  <span className="text-xs font-bold uppercase">{a.type.replace(/_/g, ' ')}</span>
                  <span className="ml-2 text-xs opacity-80">{a.message}</span>
                </div>
                <span className="shrink-0 text-xs opacity-60">
                  {new Date(a.timestamp).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

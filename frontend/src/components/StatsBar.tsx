import { useEffect, useState } from 'react'
import { checkHealth, type HealthResponse } from '../api'

interface Stat {
  label: string
  value: string
  status: 'ok' | 'warn' | 'err'
}

export function StatsBar() {
  const [health, setHealth] = useState<HealthResponse | null>(null)

  useEffect(() => {
    const poll = async () => {
      try {
        setHealth(await checkHealth())
      } catch {
        setHealth(null)
      }
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => clearInterval(interval)
  }, [])

  const stats: Stat[] = [
    {
      label: 'Status',
      value: health?.status ?? 'offline',
      status: health ? 'ok' : 'err',
    },
    {
      label: 'Version',
      value: health?.version ?? '—',
      status: 'ok',
    },
    {
      label: 'Model',
      value: health?.model_loaded ? 'Loaded' : 'Not Loaded',
      status: health?.model_loaded ? 'ok' : 'err',
    },
    {
      label: 'Database',
      value: health?.database_connected ? 'Connected' : 'Disconnected',
      status: health?.database_connected ? 'ok' : 'warn',
    },
  ]

  const colors = {
    ok: 'text-green-400',
    warn: 'text-yellow-400',
    err: 'text-red-400',
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((s) => (
        <div
          key={s.label}
          className="rounded-xl border border-zinc-800 bg-zinc-900/50 px-4 py-3"
        >
          <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            {s.label}
          </div>
          <div className={`mt-1 text-lg font-semibold ${colors[s.status]}`}>
            {s.value}
          </div>
        </div>
      ))}
    </div>
  )
}

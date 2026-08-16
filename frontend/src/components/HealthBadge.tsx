import { useEffect, useState } from 'react'
import { checkHealth, type HealthResponse } from '../api'

export function HealthBadge() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const poll = async () => {
      try {
        const h = await checkHealth()
        setHealth(h)
      } catch {
        setHealth(null)
      } finally {
        setLoading(false)
      }
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-400">
        <span className="h-2 w-2 animate-pulse rounded-full bg-yellow-500" />
        Connecting…
      </span>
    )
  }

  if (!health) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full bg-red-950 px-3 py-1 text-xs text-red-400">
        <span className="h-2 w-2 rounded-full bg-red-500" />
        API Offline
      </span>
    )
  }

  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex items-center gap-2 rounded-full bg-green-950 px-3 py-1 text-xs text-green-400">
        <span className="h-2 w-2 rounded-full bg-green-500" />
        API {health.version}
      </span>
      <span className="inline-flex items-center gap-2 rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-400">
        <span
          className={`h-2 w-2 rounded-full ${health.database_connected ? 'bg-green-500' : 'bg-red-500'}`}
        />
        DB {health.database_connected ? 'Connected' : 'Disconnected'}
      </span>
      <span className="inline-flex items-center gap-2 rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-400">
        Model: {health.model_loaded ? '✅' : '❌'}
      </span>
    </div>
  )
}

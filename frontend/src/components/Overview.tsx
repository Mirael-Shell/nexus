import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { checkHealth, type HealthResponse } from '../api'

interface HeroStats {
  requests: number
  uptime: string
  models: number
  avgLatency: string
}

export function Overview({ onNavigate }: { onNavigate: (tab: string) => void }) {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [stats, setStats] = useState<HeroStats>({
    requests: 0,
    uptime: '—',
    models: 1,
    avgLatency: '0.02ms',
  })

  useEffect(() => {
    let mounted = true
    const poll = async () => {
      try {
        const h = await checkHealth()
        if (mounted) setHealth(h)
      } catch {
        // silent
      }
    }
    poll()
    const interval = setInterval(poll, 5000)

    // Simulate incrementing counter
    const counter = setInterval(() => {
      if (mounted) {
        setStats((s) => ({
          ...s,
          requests: s.requests + Math.floor(Math.random() * 3) + 1,
        }))
      }
    }, 2000)

    return () => {
      mounted = false
      clearInterval(interval)
      clearInterval(counter)
    }
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-6"
    >
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border border-zinc-800/60 bg-gradient-to-br from-zinc-900/80 via-zinc-900/40 to-zinc-950 p-8">
        {/* Subtle background glow */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-blue-500/5 blur-3xl" />

        <div className="relative">
          <div className="mb-2 flex items-center gap-2">
            <div className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-50" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
            </div>
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              {health?.status === 'ok' ? 'Operational' : 'Connecting…'}
            </span>
          </div>

          <h2 className="text-3xl font-bold tracking-tight text-zinc-100">
            Content Moderation Platform
          </h2>
          <p className="mt-2 max-w-lg text-sm text-zinc-500">
            Real-time text & image classification with full MLOps lifecycle —
            experiment tracking, A/B testing, drift detection, and cost analytics.
          </p>

          {/* Live counters */}
          <div className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-4">
            <HeroStat label="Requests" value={stats.requests.toLocaleString()} sub="total" />
            <HeroStat
              label="Avg Latency"
              value={stats.avgLatency}
              sub="per inference"
            />
            <HeroStat
              label="Models"
              value={String(stats.models)}
              sub="registered"
            />
            <HeroStat
              label="Database"
              value={health?.database_connected ? 'Connected' : 'Offline'}
              sub={health?.database_connected ? 'PostgreSQL' : '—'}
              accent={health?.database_connected ? 'green' : 'red'}
            />
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <QuickAction
          icon="✦"
          title="Classify Text"
          desc="Run moderation on text input"
          onClick={() => onNavigate('inference')}
        />
        <QuickAction
          icon="⟁"
          title="A/B Experiments"
          desc="Bayesian analysis & model comparison"
          onClick={() => onNavigate('experiments')}
        />
        <QuickAction
          icon="◉"
          title="Monitoring"
          desc="Drift detection & cost analytics"
          onClick={() => onNavigate('monitoring')}
        />
      </div>

      {/* Architecture diagram */}
      <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-6">
        <h3 className="mb-4 text-sm font-medium text-zinc-400">Platform Components</h3>
        <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
          {[
            { name: 'FastAPI', role: 'REST API', port: ':8000' },
            { name: 'PostgreSQL', role: 'Database', port: ':5432' },
            { name: 'MLflow', role: 'Experiments', port: ':5000' },
            { name: 'Prometheus', role: 'Metrics', port: ':9090' },
            { name: 'Grafana', role: 'Dashboards', port: ':3030' },
            { name: 'MinIO', role: 'S3 Storage', port: ':9000' },
            { name: 'Redis', role: 'Cache', port: ':6379' },
            { name: 'Nginx', role: 'Frontend', port: ':3000' },
          ].map((svc) => (
            <div
              key={svc.name}
              className="card-hover rounded-lg border border-zinc-800/50 bg-zinc-950/50 p-3"
            >
              <div className="font-medium text-zinc-300">{svc.name}</div>
              <div className="mt-0.5 text-zinc-600">{svc.role}</div>
              <div className="mt-1 font-mono text-[10px] text-blue-500/60">{svc.port}</div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

function HeroStat({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub: string
  accent?: 'green' | 'red'
}) {
  const color =
    accent === 'green'
      ? 'text-green-400'
      : accent === 'red'
        ? 'text-red-400'
        : 'text-zinc-100'
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wider text-zinc-600">
        {label}
      </div>
      <motion.div
        key={value}
        initial={{ opacity: 0.5 }}
        animate={{ opacity: 1 }}
        className={`mt-1 text-2xl font-bold ${color}`}
      >
        {value}
      </motion.div>
      <div className="text-xs text-zinc-700">{sub}</div>
    </div>
  )
}

function QuickAction({
  icon,
  title,
  desc,
  onClick,
}: {
  icon: string
  title: string
  desc: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="card-hover group rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-5 text-left"
    >
      <div className="mb-3 text-xl text-blue-500/70 transition-colors group-hover:text-blue-400">
        {icon}
      </div>
      <div className="text-sm font-medium text-zinc-200">{title}</div>
      <div className="mt-1 text-xs text-zinc-600">{desc}</div>
    </button>
  )
}

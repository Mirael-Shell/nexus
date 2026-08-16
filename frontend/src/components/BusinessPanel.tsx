import { useState, useEffect } from 'react'

interface DashboardData {
  moderation_quality: {
    total_feedback: number
    correct: number
    incorrect: number
    precision: number
    satisfaction_rate: number
  }
  funnel: {
    total_predictions: number
    total_filtered: number
    allowed: number
    blocked: number
    flagged: number
    block_rate: number
  }
  label_distribution: {
    labels: Record<string, number>
    total: number
    percentages: Record<string, number>
  }
  feedback_summary: Record<string, {
    total_predictions: number
    correct: number
    incorrect: number
    per_label_precision: number | null
  }>
  false_positive_cost: {
    false_positives: number
    cost_per_fp_usd: number
    total_fp_cost_usd: number
    fp_rate: number
  }
}

export function BusinessPanel() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/v1/business/dashboard')
      .then((r) => r.json())
      .then((d) => setData(d))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="py-8 text-center text-sm text-zinc-600">Loading business metrics…</div>
  if (!data) return null

  return (
    <div className="space-y-4">
      <div>
        <h2 className="mb-1 text-lg font-semibold text-zinc-100">Business Dashboard</h2>
        <p className="text-xs text-zinc-500">Product analytics · precision · funnel · cost analysis</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Precision', value: `${(data.moderation_quality.precision * 100).toFixed(0)}%`, sub: `${data.moderation_quality.total_feedback} reviews`, color: 'text-blue-400' },
          { label: 'Block Rate', value: `${(data.funnel.block_rate * 100).toFixed(0)}%`, sub: `${data.funnel.blocked} blocked`, color: 'text-red-400' },
          { label: 'FP Cost', value: `$${data.false_positive_cost.total_fp_cost_usd.toFixed(2)}`, sub: `${data.false_positive_cost.false_positives} false pos.`, color: 'text-orange-400' },
          { label: 'FP Rate', value: `${(data.false_positive_cost.fp_rate * 100).toFixed(0)}%`, sub: 'of all feedback', color: 'text-yellow-400' },
        ].map((kpi) => (
          <div key={kpi.label} className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3 text-center">
            <div className={`text-2xl font-bold ${kpi.color}`}>{kpi.value}</div>
            <div className="text-xs uppercase tracking-wider text-zinc-500">{kpi.label}</div>
            <div className="text-xs text-zinc-600">{kpi.sub}</div>
          </div>
        ))}
      </div>

      {/* Funnel */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">Moderation Funnel</h3>
        <div className="space-y-2">
          {[
            { label: 'Total Predictions', value: data.funnel.total_predictions, max: data.funnel.total_predictions, color: 'bg-zinc-600' },
            { label: 'Filter Events', value: data.funnel.total_filtered, max: data.funnel.total_predictions, color: 'bg-blue-600' },
            { label: 'Allowed', value: data.funnel.allowed, max: data.funnel.total_predictions, color: 'bg-green-600' },
            { label: 'Blocked', value: data.funnel.blocked, max: data.funnel.total_predictions, color: 'bg-red-600' },
            { label: 'Flagged', value: data.funnel.flagged, max: data.funnel.total_predictions, color: 'bg-yellow-600' },
          ].map((row) => (
            <div key={row.label} className="flex items-center gap-3">
              <span className="w-32 shrink-0 text-xs text-zinc-400">{row.label}</span>
              <div className="h-6 flex-1 overflow-hidden rounded bg-zinc-950">
                <div
                  className={`flex h-full items-center justify-end rounded px-2 ${row.color}`}
                  style={{ width: `${row.max > 0 ? Math.max((row.value / row.max) * 100, 2) : 0}%` }}
                >
                  <span className="text-xs font-medium text-white">{row.value}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Label Distribution */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">Label Distribution</h3>
          {Object.entries(data.label_distribution.labels).length === 0 ? (
            <p className="text-sm text-zinc-600">No predictions yet</p>
          ) : (
            <div className="space-y-2">
              {Object.entries(data.label_distribution.percentages).map(([label, pct]) => (
                <div key={label}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-zinc-400 capitalize">{label}</span>
                    <span className="text-zinc-500">{(pct * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-zinc-950">
                    <div
                      className={`h-full ${label === 'safe' ? 'bg-green-600' : label === 'spam' ? 'bg-red-600' : 'bg-orange-600'}`}
                      style={{ width: `${pct * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Per-Label Precision */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">Per-Label Quality</h3>
          {Object.entries(data.feedback_summary).map(([label, info]) => (
            <div key={label} className="mb-2 flex items-center justify-between border-b border-zinc-800 pb-2 text-xs">
              <span className="text-zinc-400 capitalize">{label}</span>
              <div className="flex gap-3">
                <span className="text-green-400">✓{info.correct}</span>
                <span className="text-red-400">✗{info.incorrect}</span>
                <span className="text-zinc-500">
                  {info.per_label_precision !== null
                    ? `${(info.per_label_precision * 100).toFixed(0)}%`
                    : '—'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

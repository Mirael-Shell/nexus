import { useEffect, useState } from 'react'
import { getCostSummary, type CostSummary } from '../api'

export function CostPanel() {
  const [summary, setSummary] = useState<CostSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    try {
      const data = await getCostSummary(7)
      setSummary(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load cost data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-zinc-100">Cost Analytics</h2>
        <div className="animate-pulse text-sm text-zinc-500">Loading…</div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-100">Cost Analytics</h2>
        <button
          onClick={refresh}
          className="rounded-lg border border-zinc-700 px-3 py-1 text-xs text-zinc-400 transition hover:border-zinc-500"
        >
          ↻
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          ⚠ {error}
        </div>
      )}

      {summary && (
        <div className="space-y-4">
          {/* Top metrics */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded border border-zinc-800 p-3">
              <div className="text-xs text-zinc-600">Revenue</div>
              <div className="text-lg font-semibold text-green-400">
                ${summary.total_revenue_usd.toFixed(4)}
              </div>
            </div>
            <div className="rounded border border-zinc-800 p-3">
              <div className="text-xs text-zinc-600">Cost</div>
              <div className="text-lg font-semibold text-red-400">
                ${summary.total_cost_usd.toFixed(4)}
              </div>
            </div>
            <div className="rounded border border-zinc-800 p-3">
              <div className="text-xs text-zinc-600">Profit</div>
              <div
                className={`text-lg font-semibold ${
                  summary.total_profit_usd >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                ${summary.total_profit_usd.toFixed(4)}
              </div>
            </div>
            <div className="rounded border border-zinc-800 p-3">
              <div className="text-xs text-zinc-600">Margin</div>
              <div className="text-lg font-semibold text-zinc-300">
                {summary.avg_margin_pct.toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Unit economics */}
          <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
            <h3 className="mb-2 text-xs font-medium text-zinc-600">Unit Economics</h3>
            <div className="flex flex-wrap gap-4 text-sm">
              <span className="text-zinc-600">
                Total predictions:{' '}
                <span className="text-zinc-300">{summary.total_predictions}</span>
              </span>
              <span className="text-zinc-600">
                Cost / 1K:{' '}
                <span className="text-zinc-300">
                  ${summary.cost_per_1k_predictions_usd.toFixed(4)}
                </span>
              </span>
              <span className="text-zinc-600">
                Avg daily cost:{' '}
                <span className="text-zinc-300">
                  ${summary.avg_daily_cost_usd.toFixed(4)}
                </span>
              </span>
            </div>
          </div>

          {/* Daily breakdown */}
          {summary.daily.length > 0 && (
            <div>
              <h3 className="mb-2 text-xs font-medium text-zinc-600">Daily Breakdown</h3>
              <div className="space-y-1">
                {summary.daily.map((d) => (
                  <div
                    key={d.date}
                    className="flex items-center justify-between rounded border border-zinc-800 px-3 py-2 text-xs"
                  >
                    <span className="text-zinc-500">{d.date}</span>
                    <div className="flex items-center gap-4">
                      <span className="text-zinc-600">
                        {d.total_predictions} preds
                      </span>
                      <span className="text-red-400">
                        ${d.total_cost_usd.toFixed(4)}
                      </span>
                      <span className="text-green-400">
                        ${d.revenue_usd.toFixed(4)}
                      </span>
                      <span
                        className={
                          d.profit_usd >= 0 ? 'text-green-400' : 'text-red-400'
                        }
                      >
                        ${d.profit_usd.toFixed(4)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {summary.daily.length === 0 && (
            <div className="py-4 text-center text-sm text-zinc-600">
              No prediction data yet for cost analysis.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import { analyzeDrift, type DriftReport } from '../api'

const SEVERITY_STYLES: Record<string, string> = {
  none: 'bg-green-950 text-green-400 border-green-800',
  low: 'bg-yellow-950 text-yellow-400 border-yellow-800',
  medium: 'bg-orange-950 text-orange-400 border-orange-800',
  high: 'bg-red-950 text-red-400 border-red-800',
}

export function DriftPanel() {
  const [report, setReport] = useState<DriftReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await analyzeDrift()
      setReport(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Drift analysis failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-100">Drift Detection</h2>
        <button
          onClick={run}
          disabled={loading}
          className="rounded-lg border border-zinc-700 px-3 py-1 text-xs text-zinc-400 transition hover:border-zinc-500 disabled:opacity-50"
        >
          {loading ? 'Analyzing…' : '↻ Run Analysis'}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          ⚠ {error}
        </div>
      )}

      {report && (
        <div className="space-y-4">
          {/* Severity badge */}
          <div className="flex items-center gap-3">
            <span
              className={`rounded-full border px-3 py-1 text-sm font-medium ${
                SEVERITY_STYLES[report.severity] ?? SEVERITY_STYLES.none
              }`}
            >
              {report.severity.toUpperCase()}
            </span>
            <span className="text-sm text-zinc-500">
              Score: {report.overall_drift_score.toFixed(4)}
            </span>
          </div>

          <p className="text-sm text-zinc-400">{report.recommendation}</p>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded border border-zinc-800 p-3">
              <div className="text-xs text-zinc-600">Reference window</div>
              <div className="text-lg font-semibold text-zinc-300">
                {report.reference_size} samples
              </div>
            </div>
            <div className="rounded border border-zinc-800 p-3">
              <div className="text-xs text-zinc-600">Current window</div>
              <div className="text-lg font-semibold text-zinc-300">
                {report.window_size} samples
              </div>
            </div>
          </div>

          {/* Metrics */}
          {report.metrics.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-medium text-zinc-600">Statistical Tests</h3>
              {report.metrics.map((m) => (
                <div
                  key={m.name}
                  className={`rounded border p-3 ${
                    m.is_drifted
                      ? 'border-red-900 bg-red-950/30'
                      : 'border-zinc-800 bg-zinc-950'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-zinc-300">
                      {m.name}
                    </span>
                    <span
                      className={`text-xs font-medium ${
                        m.is_drifted ? 'text-red-400' : 'text-green-400'
                      }`}
                    >
                      {m.is_drifted ? '⚠ DRIFTED' : '✓ stable'}
                    </span>
                  </div>
                  <div className="mt-1 flex gap-4 text-xs text-zinc-600">
                    <span>
                      statistic: <span className="text-zinc-400">{m.value.toFixed(4)}</span>
                    </span>
                    <span>
                      p-value: <span className="text-zinc-400">{m.p_value.toFixed(6)}</span>
                    </span>
                    <span>
                      threshold: <span className="text-zinc-400">{m.threshold}</span>
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-zinc-700">{m.description}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!report && !loading && (
        <div className="py-8 text-center text-sm text-zinc-600">
          Click "Run Analysis" to check for data and prediction drift.
        </div>
      )}
    </div>
  )
}

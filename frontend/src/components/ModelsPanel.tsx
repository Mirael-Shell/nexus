import { useCallback, useEffect, useState } from 'react'
import { listModels, promoteModel, type ModelVersion } from '../api'

const STAGE_STYLES: Record<string, string> = {
  Production: 'bg-green-950 text-green-400 border-green-800',
  Staging: 'bg-yellow-950 text-yellow-400 border-yellow-800',
  Archived: 'bg-zinc-800 text-zinc-500 border-zinc-700',
  None: 'bg-zinc-800 text-zinc-500 border-zinc-700',
}

export function ModelsPanel() {
  const [models, setModels] = useState<ModelVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [promoting, setPromoting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await listModels()
      setModels(data.versions)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load models')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handlePromote = async (version: string, stage: string) => {
    setPromoting(version)
    try {
      await promoteModel(version, stage)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Promotion failed')
    } finally {
      setPromoting(null)
    }
  }

  const fmtDate = (ts: number | null) => {
    if (!ts) return '—'
    return new Date(ts).toLocaleString()
  }

  const fmtMetric = (key: string, val: number) => {
    if (key.includes('accuracy') || key.includes('f1') || key.includes('loss')) {
      return val.toFixed(4)
    }
    return String(val)
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-zinc-100">Model Registry</h2>
        <div className="animate-pulse text-sm text-zinc-500">Loading models…</div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-100">Model Registry</h2>
        <button
          onClick={refresh}
          className="rounded-lg border border-zinc-700 px-3 py-1 text-xs text-zinc-400 transition hover:border-zinc-500 hover:text-zinc-200"
        >
          ↻ Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          ⚠ {error}
        </div>
      )}

      {models.length === 0 ? (
        <div className="py-8 text-center text-sm text-zinc-600">
          <p className="mb-2">No models registered yet.</p>
          <p className="text-xs">
            Run <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-400">make train</code> to
            train and register a model.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {models.map((m) => (
            <div
              key={m.version}
              className="rounded-lg border border-zinc-800 bg-zinc-950 p-4"
            >
              {/* Header row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-zinc-200">
                    v{m.version}
                  </span>
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${STAGE_STYLES[m.stage] ?? STAGE_STYLES.None}`}
                  >
                    {m.stage || 'None'}
                  </span>
                </div>
                <span className="text-xs text-zinc-600">
                  {fmtDate(m.created_at)}
                </span>
              </div>

              {/* Metrics */}
              {Object.keys(m.metrics).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-4">
                  {Object.entries(m.metrics)
                    .filter(([k]) => !k.startsWith('epoch'))
                    .slice(0, 6)
                    .map(([key, val]) => (
                      <div key={key}>
                        <span className="text-xs text-zinc-600">{key}</span>
                        <span className="ml-1.5 text-sm font-medium text-zinc-300">
                          {fmtMetric(key, val)}
                        </span>
                      </div>
                    ))}
                </div>
              )}

              {/* Params */}
              {Object.keys(m.params).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-zinc-600">
                  {Object.entries(m.params)
                    .slice(0, 4)
                    .map(([key, val]) => (
                      <span key={key}>
                        {key}: <span className="text-zinc-400">{val}</span>
                      </span>
                    ))}
                </div>
              )}

              {/* Actions */}
              <div className="mt-3 flex items-center gap-2 border-t border-zinc-800 pt-3">
                {m.stage !== 'Production' && (
                  <button
                    onClick={() => handlePromote(m.version, 'Production')}
                    disabled={promoting === m.version}
                    className="rounded-lg border border-green-800 px-3 py-1 text-xs text-green-400 transition hover:bg-green-950 disabled:opacity-50"
                  >
                    {promoting === m.version ? 'Promoting…' : '→ Production'}
                  </button>
                )}
                {m.stage !== 'Staging' && m.stage !== 'Production' && (
                  <button
                    onClick={() => handlePromote(m.version, 'Staging')}
                    disabled={promoting === m.version}
                    className="rounded-lg border border-yellow-800 px-3 py-1 text-xs text-yellow-400 transition hover:bg-yellow-950 disabled:opacity-50"
                  >
                    → Staging
                  </button>
                )}
                {m.stage !== 'Archived' && (
                  <button
                    onClick={() => handlePromote(m.version, 'Archived')}
                    disabled={promoting === m.version}
                    className="rounded-lg border border-zinc-700 px-3 py-1 text-xs text-zinc-500 transition hover:text-zinc-300 disabled:opacity-50"
                  >
                    Archive
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

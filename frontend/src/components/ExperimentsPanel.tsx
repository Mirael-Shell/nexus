import { useCallback, useEffect, useState } from 'react'
import {
  analyzeExperiment,
  createExperiment,
  listExperiments,
  startExperiment,
  stopExperiment,
  type BayesianAnalysis,
  type Experiment,
} from '../api'

const STATUS_STYLES: Record<string, string> = {
  running: 'bg-green-950 text-green-400 border-green-800',
  draft: 'bg-blue-950 text-blue-400 border-blue-800',
  completed: 'bg-purple-950 text-purple-400 border-purple-800',
  stopped: 'bg-zinc-800 text-zinc-500 border-zinc-700',
}

export function ExperimentsPanel() {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<Record<string, BayesianAnalysis>>({})
  const [showCreate, setShowCreate] = useState(false)
  const [analyzing, setAnalyzing] = useState<string | null>(null)

  // Create form state
  const [name, setName] = useState('')
  const [controlModel, setControlModel] = useState('mock-v0.1.0')
  const [treatmentModel, setTreatmentModel] = useState('mock-v0.1.0')
  const [trafficSplit, setTrafficSplit] = useState(50)

  const refresh = useCallback(async () => {
    try {
      const data = await listExperiments()
      setExperiments(data.experiments)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load experiments')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleCreate = async () => {
    try {
      await createExperiment({
        name,
        control_model: controlModel,
        treatment_model: treatmentModel,
        traffic_split: trafficSplit,
      })
      setName('')
      setShowCreate(false)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Create failed')
    }
  }

  const handleStart = async (id: string) => {
    try {
      await startExperiment(id)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Start failed')
    }
  }

  const handleStop = async (id: string) => {
    try {
      await stopExperiment(id)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Stop failed')
    }
  }

  const handleAnalyze = async (id: string) => {
    setAnalyzing(id)
    try {
      const result = await analyzeExperiment(id)
      setAnalysis((prev) => ({ ...prev, [id]: result }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setAnalyzing(null)
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-zinc-100">A/B Experiments</h2>
        <div className="animate-pulse text-sm text-zinc-500">Loading…</div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-100">A/B Experiments</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="rounded-lg border border-blue-800 px-3 py-1 text-xs text-blue-400 transition hover:bg-blue-950"
          >
            {showCreate ? 'Cancel' : '+ New'}
          </button>
          <button
            onClick={refresh}
            className="rounded-lg border border-zinc-700 px-3 py-1 text-xs text-zinc-400 transition hover:border-zinc-500"
          >
            ↻
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          ⚠ {error}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="mb-4 space-y-3 rounded-lg border border-zinc-700 bg-zinc-950 p-4">
          <input
            type="text"
            placeholder="Experiment name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200"
          />
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs text-zinc-600">Control model</label>
              <input
                type="text"
                value={controlModel}
                onChange={(e) => setControlModel(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-zinc-600">Treatment model</label>
              <input
                type="text"
                value={treatmentModel}
                onChange={(e) => setTreatmentModel(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-zinc-600">
              Traffic to treatment: {trafficSplit}%
            </label>
            <input
              type="range"
              min="0"
              max="100"
              value={trafficSplit}
              onChange={(e) => setTrafficSplit(Number(e.target.value))}
              className="w-full accent-blue-500"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={!name.trim()}
            className="w-full rounded-lg bg-blue-600 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            Create Experiment
          </button>
        </div>
      )}

      {/* Experiment list */}
      {experiments.length === 0 ? (
        <div className="py-8 text-center text-sm text-zinc-600">
          No experiments yet. Create one to start A/B testing.
        </div>
      ) : (
        <div className="space-y-3">
          {experiments.map((exp) => {
            const a = analysis[exp.id]
            return (
              <div
                key={exp.id}
                className="rounded-lg border border-zinc-800 bg-zinc-950 p-4"
              >
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-zinc-200">{exp.name}</span>
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                        STATUS_STYLES[exp.status] ?? STATUS_STYLES.stopped
                      }`}
                    >
                      {exp.status}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {exp.status === 'draft' && (
                      <button
                        onClick={() => handleStart(exp.id)}
                        className="rounded border border-green-800 px-2 py-0.5 text-xs text-green-400 hover:bg-green-950"
                      >
                        Start
                      </button>
                    )}
                    {exp.status === 'running' && (
                      <button
                        onClick={() => handleStop(exp.id)}
                        className="rounded border border-red-800 px-2 py-0.5 text-xs text-red-400 hover:bg-red-950"
                      >
                        Stop
                      </button>
                    )}
                    <button
                      onClick={() => handleAnalyze(exp.id)}
                      disabled={analyzing === exp.id}
                      className="rounded border border-zinc-700 px-2 py-0.5 text-xs text-zinc-400 hover:border-zinc-500 disabled:opacity-50"
                    >
                      {analyzing === exp.id ? '…' : 'Analyze'}
                    </button>
                  </div>
                </div>

                {/* Models + split */}
                <div className="mt-2 flex items-center gap-4 text-xs text-zinc-600">
                  <span>
                    Control: <span className="text-zinc-400">{exp.control_model}</span>
                  </span>
                  <span>→</span>
                  <span>
                    Treatment: <span className="text-zinc-400">{exp.treatment_model}</span>
                  </span>
                  <span className="text-zinc-700">|</span>
                  <span>{exp.traffic_split}% treatment</span>
                  <span className="text-zinc-700">|</span>
                  <span>{exp.strategy}</span>
                </div>

                {/* Stats */}
                <div className="mt-3 grid grid-cols-2 gap-4">
                  <div className="rounded border border-zinc-800 p-2">
                    <div className="mb-1 text-xs text-zinc-600">Control</div>
                    <div className="flex gap-3 text-sm">
                      <span className="text-green-400">↑{exp.control_up}</span>
                      <span className="text-red-400">↓{exp.control_down}</span>
                      <span className="text-zinc-600">/{exp.control_total}</span>
                    </div>
                  </div>
                  <div className="rounded border border-zinc-800 p-2">
                    <div className="mb-1 text-xs text-zinc-600">Treatment</div>
                    <div className="flex gap-3 text-sm">
                      <span className="text-green-400">↑{exp.treatment_up}</span>
                      <span className="text-red-400">↓{exp.treatment_down}</span>
                      <span className="text-zinc-600">/{exp.treatment_total}</span>
                    </div>
                  </div>
                </div>

                {/* Bayesian Analysis */}
                {a && (
                  <div className="mt-3 space-y-2 rounded border border-blue-900/50 bg-blue-950/20 p-3">
                    <div className="text-xs font-medium text-blue-400">
                      Bayesian Analysis
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-zinc-600">Control rate:</span>
                        <span className="ml-1 text-zinc-300">
                          {(a.control.posterior_mean * 100).toFixed(1)}%
                        </span>
                        <span className="ml-1 text-zinc-700">
                          [{(a.control.ci_95[0] * 100).toFixed(0)}–{(a.control.ci_95[1] * 100).toFixed(0)}%]
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-600">Treatment rate:</span>
                        <span className="ml-1 text-zinc-300">
                          {(a.treatment.posterior_mean * 100).toFixed(1)}%
                        </span>
                        <span className="ml-1 text-zinc-700">
                          [{(a.treatment.ci_95[0] * 100).toFixed(0)}–{(a.treatment.ci_95[1] * 100).toFixed(0)}%]
                        </span>
                      </div>
                    </div>
                    <div className="text-xs">
                      <span className="text-zinc-600">P(treatment better):</span>
                      <span className="ml-1 font-medium text-blue-400">
                        {(a.prob_treatment_better * 100).toFixed(1)}%
                      </span>
                    </div>
                    {/* Progress bar for P(treatment better) */}
                    <div className="h-1.5 overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all"
                        style={{ width: `${a.prob_treatment_better * 100}%` }}
                      />
                    </div>
                    <div
                      className={`rounded px-2 py-1 text-xs font-medium ${
                        a.should_stop
                          ? 'bg-green-950 text-green-400'
                          : 'bg-zinc-900 text-zinc-400'
                      }`}
                    >
                      {a.should_stop ? '✓ ' : '⟳ '}
                      {a.reason}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

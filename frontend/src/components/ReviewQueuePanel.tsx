import { useState, useEffect, useCallback } from 'react'

interface UncertainSample {
  prediction_id: string
  text: string
  predicted_label: string
  confidence: number
  all_probabilities: Record<string, number>
  entropy: number
  created_at: string
}

const LABEL_STYLES: Record<string, string> = {
  safe: 'bg-green-950 text-green-400 border-green-800',
  spam: 'bg-red-950 text-red-400 border-red-800',
  toxic: 'bg-orange-950 text-orange-400 border-orange-800',
}

export function ReviewQueuePanel() {
  const [samples, setSamples] = useState<UncertainSample[]>([])
  const [totalLow, setTotalLow] = useState(0)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState<string | null>(null)
  const [labeled, setLabeled] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/v1/active-learning/uncertain?limit=10&threshold=0.5')
      const data = await res.json()
      setSamples(data.samples || [])
      setTotalLow(data.total_low_confidence || 0)
    } catch {
      // ignore
    }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const review = async (sample: UncertainSample, label: string) => {
    setSubmitting(sample.prediction_id)
    try {
      await fetch('/api/v1/active-learning/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prediction_id: sample.prediction_id, correct_label: label }),
      })
      setSamples((prev) => prev.filter((s) => s.prediction_id !== sample.prediction_id))
      setLabeled((n) => n + 1)
    } finally {
      setSubmitting(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Review Queue</h2>
          <p className="text-xs text-zinc-500">
            Active learning · {totalLow} low-confidence predictions · {labeled} labeled this session
          </p>
        </div>
        <button
          onClick={load}
          className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-400 hover:text-zinc-200"
        >
          ↻ Refresh
        </button>
      </div>

      {loading ? (
        <div className="py-8 text-center text-sm text-zinc-600">Loading uncertain samples…</div>
      ) : samples.length === 0 ? (
        <div className="py-8 text-center text-sm text-zinc-600">
          ✅ No uncertain samples to review. The model is confident!
        </div>
      ) : (
        <div className="space-y-3">
          {samples.map((s) => (
            <div key={s.prediction_id} className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
              <div className="mb-3 flex items-start justify-between gap-3">
                <p className="text-sm text-zinc-200">{s.text}</p>
                <span className={`shrink-0 rounded border px-2 py-0.5 text-xs font-bold ${LABEL_STYLES[s.predicted_label] ?? ''}`}>
                  {s.predicted_label}
                </span>
              </div>

              {/* Confidence bar */}
              <div className="mb-3">
                <div className="mb-1 flex justify-between text-xs text-zinc-500">
                  <span>Confidence: {(s.confidence * 100).toFixed(1)}%</span>
                  <span>Entropy: {s.entropy.toFixed(3)}</span>
                </div>
                <div className="flex gap-1">
                  {Object.entries(s.all_probabilities).map(([label, prob]) => (
                    <div key={label} className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className={`h-full ${label === 'safe' ? 'bg-green-600' : label === 'spam' ? 'bg-red-600' : 'bg-orange-600'}`}
                        style={{ width: `${prob * 100}%` }}
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Label buttons */}
              <div className="flex gap-2">
                {['safe', 'spam', 'toxic'].map((label) => (
                  <button
                    key={label}
                    onClick={() => review(s, label)}
                    disabled={submitting === s.prediction_id}
                    className={`flex-1 rounded-lg border py-1.5 text-sm font-medium transition disabled:opacity-40 ${
                      label === 'safe'
                        ? 'border-green-800 text-green-400 hover:bg-green-950'
                        : label === 'spam'
                        ? 'border-red-800 text-red-400 hover:bg-red-950'
                        : 'border-orange-800 text-orange-400 hover:bg-orange-950'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

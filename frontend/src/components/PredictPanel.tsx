import { useState } from 'react'
import { predict, sendFeedback, addExample, retrainModel, type PredictResponse } from '../api'

const LABEL_STYLES: Record<string, string> = {
  safe: 'bg-green-950 text-green-400 border-green-800',
  spam: 'bg-yellow-950 text-yellow-400 border-yellow-800',
  toxic: 'bg-red-950 text-red-400 border-red-800',
}

export function PredictPanel() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [showCorrect, setShowCorrect] = useState(false)
  const [correctLabel, setCorrectLabel] = useState<string>('spam')
  const [correctMsg, setCorrectMsg] = useState<string | null>(null)
  const [retraining, setRetraining] = useState(false)
  const [retrainMsg, setRetrainMsg] = useState<string | null>(null)

  const handlePredict = async () => {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    setFeedbackSent(false)
    setShowCorrect(false)
    setCorrectMsg(null)
    setRetrainMsg(null)
    try {
      const r = await predict(text)
      setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async (type: 'up' | 'down') => {
    if (!result) return
    try {
      await sendFeedback(result.prediction_id, type)
      setFeedbackSent(true)
      if (type === 'down') {
        setShowCorrect(true)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Feedback failed')
    }
  }

  const handleCorrectLabel = async () => {
    if (!text.trim()) return
    try {
      const r = await addExample(text, correctLabel)
      setCorrectMsg(`✅ Added to dataset as "${correctLabel}". ${r.total_samples} total samples.`)
      setShowCorrect(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add example')
    }
  }

  const handleRetrain = async () => {
    setRetraining(true)
    setRetrainMsg(null)
    try {
      const r = await retrainModel()
      if (r.success) {
        setRetrainMsg(r.message)
      } else {
        setError(r.message)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Retrain failed')
    } finally {
      setRetraining(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handlePredict()
    }
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
      <h2 className="mb-4 text-lg font-semibold text-zinc-100">Content Classification</h2>

      {/* Text input */}
      <div className="space-y-3">
        <textarea
          className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600"
          rows={4}
          placeholder="Enter text to classify (e.g., 'WIN a FREE prize! Click here!')"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-zinc-600">{text.length} / 10,000 chars</span>
          <button
            onClick={handlePredict}
            disabled={loading || !text.trim()}
            className="rounded-lg bg-zinc-100 px-5 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
          >
            {loading ? 'Classifying…' : 'Classify →'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          ⚠ {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="mt-6 space-y-4">
          {/* Top result */}
          <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3">
            <div className="flex items-center gap-3">
              <span
                className={`rounded-full border px-3 py-1 text-sm font-medium uppercase tracking-wide ${LABEL_STYLES[result.label] ?? LABEL_STYLES.safe}`}
              >
                {result.label}
              </span>
              <span className="text-2xl font-bold text-zinc-100">
                {(result.confidence * 100).toFixed(1)}%
              </span>
            </div>
            <span className="text-xs text-zinc-600">{result.processing_time_ms.toFixed(2)} ms</span>
          </div>

          {/* All probabilities */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium uppercase tracking-wider text-zinc-500">
              All Probabilities
            </h3>
            {result.all_probabilities.map((p) => (
              <div key={p.label} className="flex items-center gap-3">
                <span className="w-14 text-sm text-zinc-400">{p.label}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className={`h-full rounded-full ${
                      p.label === 'safe'
                        ? 'bg-green-500'
                        : p.label === 'spam'
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                    }`}
                    style={{ width: `${p.probability * 100}%` }}
                  />
                </div>
                <span className="w-12 text-right text-sm text-zinc-500">
                  {(p.probability * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>

          {/* Feedback */}
          {!feedbackSent ? (
            <div className="flex items-center gap-3 border-t border-zinc-800 pt-4">
              <span className="text-sm text-zinc-400">Was this correct?</span>
              <button
                onClick={() => handleFeedback('up')}
                className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition hover:border-green-600 hover:text-green-400"
              >
                👍 Correct
              </button>
              <button
                onClick={() => handleFeedback('down')}
                className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-300 transition hover:border-red-600 hover:text-red-400"
              >
                👎 Wrong
              </button>
            </div>
          ) : (
            <div className="space-y-3 border-t border-zinc-800 pt-4">
              {!showCorrect && !correctMsg && (
                <div className="text-sm text-green-400">
                  ✅ Feedback recorded — thank you!
                </div>
              )}

              {/* Correct label form (shown after 👎) */}
              {showCorrect && (
                <div className="space-y-2 rounded-lg border border-zinc-800 bg-zinc-950 p-3">
                  <div className="text-sm text-zinc-400">
                    What should the correct label be?
                  </div>
                  <div className="flex items-center gap-2">
                    {(['safe', 'spam', 'toxic'] as const).map((lbl) => (
                      <button
                        key={lbl}
                        onClick={() => setCorrectLabel(lbl)}
                        className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                          correctLabel === lbl
                            ? 'border-blue-500 bg-blue-950 text-blue-400'
                            : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'
                        }`}
                      >
                        {lbl}
                      </button>
                    ))}
                    <button
                      onClick={handleCorrectLabel}
                      className="ml-auto rounded-lg bg-zinc-100 px-3 py-1.5 text-sm font-medium text-zinc-900 transition hover:bg-white"
                    >
                      Add to dataset
                    </button>
                  </div>
                </div>
              )}

              {/* Confirmation */}
              {correctMsg && (
                <div className="text-sm text-green-400">{correctMsg}</div>
              )}
            </div>
          )}

          {/* Retrain button */}
          {(correctMsg || feedbackSent) && (
            <div className="flex items-center gap-3 border-t border-zinc-800 pt-4">
              <button
                onClick={handleRetrain}
                disabled={retraining}
                className="rounded-lg border border-blue-800 bg-blue-950/50 px-4 py-2 text-sm font-medium text-blue-400 transition hover:bg-blue-900/50 disabled:opacity-50"
              >
                {retraining ? '🔄 Retraining…' : '⚡ Retrain Model'}
              </button>
              <span className="text-xs text-zinc-600">
                Retrains on updated dataset and hot-swaps the model
              </span>
            </div>
          )}

          {/* Retrain result */}
          {retrainMsg && (
            <div className="rounded-lg border border-green-900 bg-green-950/30 px-4 py-3 text-sm text-green-400">
              ✅ {retrainMsg}
            </div>
          )}

          {/* Meta */}
          <div className="flex items-center gap-4 text-xs text-zinc-600">
            <span>ID: {result.prediction_id.slice(0, 8)}…</span>
            <span>Model: {result.model_version}</span>
          </div>
        </div>
      )}
    </div>
  )
}

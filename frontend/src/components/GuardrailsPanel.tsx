import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface LayerResult {
  layer: string
  triggered: boolean
  signals: string[]
  score: number
}

interface GuardrailResponse {
  action: string
  final_score: number
  ml_label: string
  ml_confidence: number
  layers: LayerResult[]
  explanation: string
  latency_ms: number
}

const ACTION_STYLES: Record<string, string> = {
  allow: 'text-green-400 border-green-800 bg-green-950',
  block: 'text-red-400 border-red-800 bg-red-950',
  flag: 'text-yellow-400 border-yellow-800 bg-yellow-950',
}

const LAYER_META: Record<string, { icon: string; desc: string }> = {
  regex: { icon: '⚡', desc: 'URL / email / phone / CAPS' },
  lexicon: { icon: '📖', desc: 'Banned phrases list' },
  ml: { icon: '🧠', desc: 'TF-IDF + LogReg classifier' },
  embedding: { icon: '🔗', desc: 'Semantic similarity' },
}

export function GuardrailsPanel() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<GuardrailResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const analyze = async () => {
    if (!text.trim()) return
    setLoading(true)
    try {
      const res = await fetch('/api/v1/guardrails/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      setResult(await res.json())
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="mb-1 text-lg font-semibold text-zinc-100">Guardrails</h2>
        <p className="text-xs text-zinc-500">
          Multi-layer moderation: regex → lexicon → ML → embedding similarity
        </p>
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && analyze()}
          placeholder="Enter text to run through all 4 layers…"
          className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none"
        />
        <button
          onClick={analyze}
          disabled={loading || !text.trim()}
          className="rounded-lg border border-blue-700 bg-blue-950 px-4 py-2 text-sm font-medium text-blue-400 transition hover:bg-blue-900 disabled:opacity-40"
        >
          {loading ? 'Analyzing…' : 'Analyze →'}
        </button>
      </div>

      {/* Result */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-3"
          >
            {/* Verdict */}
            <div className={`rounded-xl border p-4 ${ACTION_STYLES[result.action]}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold uppercase">
                    {result.action === 'block' ? '⛔' : result.action === 'flag' ? '⚠️' : '✅'}
                  </span>
                  <div>
                    <div className="text-lg font-bold uppercase">{result.action}</div>
                    <div className="text-xs opacity-75">{result.explanation}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold">{(result.final_score * 100).toFixed(1)}%</div>
                  <div className="text-xs opacity-60">risk score</div>
                </div>
              </div>
            </div>

            {/* Layers breakdown */}
            <div className="space-y-2">
              {result.layers.map((layer) => (
                <div
                  key={layer.layer}
                  className={`rounded-lg border px-3 py-2.5 ${
                    layer.triggered
                      ? 'border-zinc-700 bg-zinc-900'
                      : 'border-zinc-800/50 bg-zinc-900/30 opacity-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span>{LAYER_META[layer.layer]?.icon ?? '🔒'}</span>
                      <span className="text-sm font-medium text-zinc-200">{layer.layer}</span>
                      <span className="text-xs text-zinc-600">{LAYER_META[layer.layer]?.desc}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {layer.triggered ? (
                        <span className="text-xs font-bold text-red-400">TRIGGERED</span>
                      ) : (
                        <span className="text-xs text-zinc-600">passed</span>
                      )}
                      <span className="text-xs text-zinc-500">{(layer.score * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  {layer.signals.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {layer.signals.map((s, i) => (
                        <span
                          key={i}
                          className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Meta */}
            <div className="flex justify-between text-xs text-zinc-600">
              <span>ML: {result.ml_label} ({(result.ml_confidence * 100).toFixed(1)}%)</span>
              <span>{result.latency_ms.toFixed(1)}ms</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Example quick-fill */}
      <div className="flex flex-wrap gap-2 pt-2">
        {[
          'Hello, great stream today!',
          'WIN FREE iPhone! Click here NOW!!!',
          'Contact me at spam@example.com www.spam.com',
          'You are absolute trash, uninstall and die',
        ].map((example) => (
          <button
            key={example}
            onClick={() => setText(example)}
            className="rounded-full border border-zinc-800 bg-zinc-900/50 px-3 py-1 text-xs text-zinc-500 transition hover:border-zinc-600 hover:text-zinc-300"
          >
            {example.length > 35 ? example.slice(0, 35) + '…' : example}
          </button>
        ))}
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import {
  filterContent,
  getFilterStats,
  type FilterResponse,
  type FilterStats,
} from '../api'

const ACTION_STYLES: Record<string, string> = {
  allow: 'bg-green-950 text-green-400 border-green-800',
  block: 'bg-red-950 text-red-400 border-red-800',
  flag: 'bg-yellow-950 text-yellow-400 border-yellow-800',
}

export function FilterPanel() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<FilterResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<FilterStats | null>(null)

  // Rules
  const [blockSpam, setBlockSpam] = useState(true)
  const [blockToxic, setBlockToxic] = useState(true)
  const [threshold, setThreshold] = useState(0.5)
  const [useSimilarity, setUseSimilarity] = useState(true)
  const [source, setSource] = useState('twitch')

  // Code example tab
  const [codeTab, setCodeTab] = useState<'curl' | 'python' | 'js'>('curl')

  useEffect(() => {
    refreshStats()
  }, [])

  const refreshStats = async () => {
    try {
      const s = await getFilterStats()
      setStats(s)
    } catch {
      // Non-critical
    }
  }

  const handleFilter = async () => {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const block_labels: string[] = []
      if (blockSpam) block_labels.push('spam')
      if (blockToxic) block_labels.push('toxic')

      const r = await filterContent({
        text,
        rules: {
          block_labels,
          flag_labels: [],
          threshold,
          use_similarity_boost: useSimilarity,
        },
        source,
      })
      setResult(r)
      refreshStats()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const codeExamples: Record<string, string> = {
    curl: `curl -X POST http://localhost:8000/api/v1/filter \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "WIN FREE iPhone! Click here!",
    "rules": {
      "block_labels": ["spam", "toxic"],
      "threshold": 0.5
    },
    "source": "twitch"
  }'`,
    python: `import httpx

r = httpx.post("http://localhost:8000/api/v1/filter", json={
    "text": "WIN FREE iPhone! Click here!",
    "rules": {
        "block_labels": ["spam", "toxic"],
        "threshold": 0.5,
    },
    "source": "twitch",
})
data = r.json()

if data["action"] == "block":
    print(f"🚫 Blocked: {data['label']} ({data['confidence']:.0%})")
elif data["action"] == "flag":
    print(f"⚠️ Flagged for review: {data['label']}")
else:
    print("✅ Allowed")`,
    js: `const res = await fetch("http://localhost:8000/api/v1/filter", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    text: "WIN FREE iPhone! Click here!",
    rules: {
      block_labels: ["spam", "toxic"],
      threshold: 0.5,
    },
    source: "twitch",
  }),
});

const data = await res.json();
// data.action = "allow" | "block" | "flag"
// data.label = "spam" | "toxic" | "safe"
// data.confidence = 0.0 - 1.0`,
  }

  return (
    <div className="space-y-6">
      {/* Filter Demo */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h2 className="mb-4 text-lg font-semibold text-zinc-100">
          Filter API — Live Demo
        </h2>

        {/* Rules */}
        <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="blockSpam"
              checked={blockSpam}
              onChange={(e) => setBlockSpam(e.target.checked)}
              className="h-4 w-4 rounded border-zinc-600 bg-zinc-900 accent-blue-500"
            />
            <label htmlFor="blockSpam" className="text-sm text-zinc-400">Block spam</label>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="blockToxic"
              checked={blockToxic}
              onChange={(e) => setBlockToxic(e.target.checked)}
              className="h-4 w-4 rounded border-zinc-600 bg-zinc-900 accent-blue-500"
            />
            <label htmlFor="blockToxic" className="text-sm text-zinc-400">Block toxic</label>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="useSim"
              checked={useSimilarity}
              onChange={(e) => setUseSimilarity(e.target.checked)}
              className="h-4 w-4 rounded border-zinc-600 bg-zinc-900 accent-blue-500"
            />
            <label htmlFor="useSim" className="text-sm text-zinc-400">Similarity boost</label>
          </div>
          <div>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-1 text-sm text-zinc-300 outline-none"
            >
              <option value="twitch">twitch</option>
              <option value="youtube">youtube</option>
              <option value="discord">discord</option>
              <option value="api">api</option>
            </select>
          </div>
        </div>

        {/* Threshold slider */}
        <div className="mb-4 flex items-center gap-3">
          <span className="text-sm text-zinc-500">Threshold:</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="h-1 w-32 cursor-pointer appearance-none rounded-full bg-zinc-700 accent-blue-500"
          />
          <span className="w-10 text-sm font-medium text-zinc-300">{threshold.toFixed(2)}</span>
        </div>

        {/* Text input */}
        <textarea
          className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-zinc-600"
          rows={3}
          placeholder="Enter message to filter (e.g., 'Click here for FREE money!')"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-zinc-600">Source: {source}</span>
          <button
            onClick={handleFilter}
            disabled={loading || !text.trim()}
            className="rounded-lg bg-zinc-100 px-5 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
          >
            {loading ? 'Filtering…' : 'Filter →'}
          </button>
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
            <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-4">
              <div className="flex items-center gap-4">
                <span
                  className={`rounded-full border px-4 py-1.5 text-base font-bold uppercase tracking-wide ${ACTION_STYLES[result.action] ?? ACTION_STYLES.allow}`}
                >
                  {result.action === 'allow' ? '✅ allow' : result.action === 'block' ? '🚫 block' : '⚠️ flag'}
                </span>
                <div>
                  <div className="text-sm text-zinc-400">Label: <span className="font-medium text-zinc-200">{result.label}</span></div>
                  <div className="text-sm text-zinc-400">Confidence: <span className="font-medium text-zinc-200">{(result.confidence * 100).toFixed(1)}%</span></div>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-zinc-600">Latency</div>
                <div className="text-lg font-bold text-zinc-300">{result.latency_ms.toFixed(1)} ms</div>
              </div>
            </div>

            {/* Triggered rules */}
            {result.triggered_rules.length > 0 && (
              <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
                <div className="mb-1 text-xs font-medium uppercase tracking-wider text-zinc-500">Triggered Rules</div>
                {result.triggered_rules.map((rule, i) => (
                  <div key={i} className="text-sm text-yellow-400">⚡ {rule}</div>
                ))}
              </div>
            )}

            {/* Similar matches */}
            {result.similar_matches.length > 0 && (
              <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
                <div className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Similar Messages Found ({result.similar_matches.length})
                </div>
                {result.similar_matches.map((m, i) => (
                  <div key={i} className="flex items-center justify-between py-1 text-sm">
                    <span className="truncate text-zinc-400">{m.text}</span>
                    <span className="ml-2 flex shrink-0 items-center gap-2">
                      <span className="text-zinc-600">{(m.similarity * 100).toFixed(0)}% match</span>
                      <span className={`rounded px-1.5 py-0.5 text-xs ${ACTION_STYLES[m.action] ?? ''}`}>{m.action}</span>
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Embedding info */}
            <div className="flex items-center gap-4 text-xs text-zinc-600">
              <span>Embedding: {result.embedding_model}</span>
              <span>Event ID: {result.event_id?.slice(0, 8) ?? '—'}…</span>
            </div>
          </div>
        )}
      </div>

      {/* Stats */}
      {stats && !stats.error && stats.total_events > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
          <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">Filter Statistics</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
              <div className="text-xs text-zinc-600">Total</div>
              <div className="text-xl font-bold text-zinc-200">{stats.total_events}</div>
            </div>
            {Object.entries(stats.by_action).map(([action, count]) => (
              <div key={action} className="rounded-lg border border-zinc-800 bg-zinc-950 p-3">
                <div className="text-xs text-zinc-600">{action}</div>
                <div className="text-xl font-bold text-zinc-200">{count}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Integration Examples */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Integration Examples
        </h3>
        <div className="mb-3 flex gap-2">
          {(['curl', 'python', 'js'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setCodeTab(tab)}
              className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                codeTab === tab
                  ? 'border-zinc-600 bg-zinc-800 text-zinc-200'
                  : 'border-zinc-800 text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {tab === 'python' ? 'Python' : tab === 'js' ? 'JavaScript' : 'cURL'}
            </button>
          ))}
        </div>
        <pre className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950 p-4 text-xs text-zinc-300">
          <code>{codeExamples[codeTab]}</code>
        </pre>
      </div>
    </div>
  )
}
